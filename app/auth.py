from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_user, login_required, logout_user, current_user, COOKIE_NAME
from werkzeug.security import generate_password_hash, check_password_hash
from functools import lru_cache, wraps
from db import *
from settings import get_settings
from flask_login import LoginManager

import hmac
import logging
import os
import re
import threading
import time

# Retrieve main logger
logger = logging.getLogger('main')

# Successful scrypt verifications, keyed by an HMAC of the stored hash and password under a
# per-process secret: a password change misses the cache, and failures are never cached.
VERIFY_CACHE_TTL = 300
VERIFY_CACHE_MAX = 512
_verify_secret = os.urandom(32)
_verify_cache = {}
_verify_lock = threading.Lock()


def verify_password(pwhash, password):
    """check_password_hash, memoizing successes so a repeat request skips scrypt."""
    key = hmac.new(_verify_secret, pwhash.encode() + b'\0' + password.encode(),
                   'sha256').digest()
    now = time.monotonic()
    with _verify_lock:
        if _verify_cache.get(key, 0) > now:
            return True
    if not check_password_hash(pwhash, password):
        return False
    with _verify_lock:
        if len(_verify_cache) >= VERIFY_CACHE_MAX:
            for expired in [k for k, e in _verify_cache.items() if e <= now]:
                del _verify_cache[expired]
            if len(_verify_cache) >= VERIFY_CACHE_MAX:
                _verify_cache.clear()
        _verify_cache[key] = now + VERIFY_CACHE_TTL
    return True

# Seconds added to every failed login, to slow password guessing.
LOGIN_FAILURE_DELAY = 1
# Verified against for an unknown user, so it costs the same scrypt as a wrong password.
_DUMMY_HASH = 'scrypt:32768:8:1$l8iBxjfRse5QrvSS$466641c1ae37e19fd60ecd4c155b3f18162889eb392297ec844c1c68259f3753f58baa429cee2984cbf64fac8da638f99dcb98f21581af173a08e7755d0d2fd2'

def check_credentials(username, password):
    """The user these credentials belong to, else None after a fixed delay."""
    password = password or ''
    user = User.query.filter_by(user=username).first()
    if user is not None and verify_password(user.password, password):
        return user
    if user is None:
        check_password_hash(_DUMMY_HASH, password)
    time.sleep(LOGIN_FAILURE_DELAY)
    return None

def validate_password(password):
    """
    Validate password according to Basic Auth specifications and Tinfoil compatibility.
    Rejects:
    - Empty passwords
    - Control characters (null, line breaks, etc.)
    - Tinfoil forbidden characters: @ & / ? # =
    - Non-UTF-8 characters
    """
    if not password:
        return False, "Password cannot be empty"
    
    # Check for control characters (null, line breaks, etc.)
    # This includes: null (\x00), tab (\x09), newline (\x0A), carriage return (\x0D), and other control chars
    control_chars = r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'
    if re.search(control_chars, password):
        return False, "Password contains invalid control characters"
    
    # Also check for tab, newline, and carriage return explicitly
    if '\t' in password or '\n' in password or '\r' in password:
        return False, "Password contains invalid control characters"
    
    # Check for Tinfoil forbidden characters
    tinfoil_forbidden = r'[@&/?#=]'
    if re.search(tinfoil_forbidden, password):
        return False, "Password contains invalid characters. Please avoid: @ & / ? # ="
    
    # Check for UTF-8 encoding validity
    try:
        password.encode('utf-8')
    except UnicodeEncodeError:
        return False, "Password contains invalid UTF-8 characters"
    
    return True, "Password is valid"

def validate_username(username):
    """
    Validate username according to Basic Auth specifications.
    Rejects:
    - Empty usernames
    - Colons (:)
    - Control characters (null, line breaks, etc.)
    - Non-UTF-8 characters
    """
    if not username:
        return False, "Username cannot be empty"
    
    # Check for colons (not allowed in Basic Auth usernames)
    if ':' in username:
        return False, "Username cannot contain colons (:)"
    
    # Check for control characters (null, line breaks, etc.)
    control_chars = r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'
    if re.search(control_chars, username):
        return False, "Username contains invalid control characters"
    
    # Also check for tab, newline, and carriage return explicitly
    if '\t' in username or '\n' in username or '\r' in username:
        return False, "Username contains invalid control characters"
    
    # Check for UTF-8 encoding validity
    try:
        username.encode('utf-8')
    except UnicodeEncodeError:
        return False, "Username contains invalid UTF-8 characters"
    
    return True, "Username is valid"

def admin_account_created():
    return len(User.query.filter_by(admin_access=True).all())

# The account init_users creates on an install with no users, to be changed at the first login.
DEFAULT_ADMIN = 'admin'
DEFAULT_PASSWORD = 'admin'

# Keyed by the stored hash, failures included (verify_password caches only successes): a
# password change stores a new hash, so this costs one scrypt per hash rather than per request.
@lru_cache(maxsize=256)
def is_default_password(pwhash):
    return check_password_hash(pwhash, DEFAULT_PASSWORD)

def unauthorized_json():
    response = login_manager.unauthorized()
    resp = {
        'success': False,
        'status_code': response.status_code,
        'location': response.location
    }
    return jsonify(resp)

def access_required(*accesses):
    """Gate a view on any one of the given accesses."""
    def _access_required(f):
        @wraps(f)
        def decorated_view(*args, **kwargs):
            if not admin_account_created():
                # Auth disabled, request ok
                return f(*args, **kwargs)

            if not current_user.is_authenticated:
                # return unauthorized_json()
                return login_manager.unauthorized()

            if not any(current_user.has_access(access) for access in accesses):
                return 'Forbidden', 403
            return f(*args, **kwargs)
        return decorated_view
    return _access_required


def roles_required(roles: list, require_all=False):
    def _roles_required(f):
        @wraps(f)
        def decorated_view(*args, **kwargs):
            if not roles:
                raise ValueError('Empty list used when requiring a role.')
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if require_all and not all(current_user.has_role(role) for role in roles):
                return 'Forbidden', 403
            elif not require_all and not any(current_user.has_role(role) for role in roles):
                return 'Forbidden', 403
            return f(*args, **kwargs)

        return decorated_view

    return _roles_required

def basic_auth(request):
    success = True
    error = ''
    user = None

    auth = request.authorization
    if auth is None:
        success = False
        error = 'No authentication provided.'
        return success, error, user

    user = check_credentials(auth.username, auth.password)
    if user is None:
        success = False
        error = 'Invalid username or password.'

    return success, error, user

def check_shop_access(request, auth=None):
    """Anyone on a public shop, else a user with shop access. `auth` reuses a basic_auth result."""
    success, error, user = auth if auth is not None else basic_auth(request)
    user = user if success else None

    if get_settings()['shop']['public']:
        return True, None, user

    if not success:
        return False, 'Shop requires authentication.\n' + error, None
    if not user.has_shop_access():
        return False, f'User {user.user} does not have access to the shop.', user
    return True, None, user

def resolve_shop_caller(request):
    """Shop gate by session cookie or Basic Auth; an admin passes without shop access."""
    if not admin_account_created():
        return True, None, None
    auth = ((True, None, current_user._get_current_object())
            if current_user.is_authenticated else basic_auth(request))

    success, error, user = check_shop_access(request, auth=auth)
    if not success and user is not None and user.has_admin_access():
        return True, None, user
    return success, error, user

def shop_access_denied(error, user):
    """403 for a known caller, 401 with a Basic Auth challenge otherwise."""
    status = 403 if user else 401
    response = jsonify({'error': error})
    if status == 401:
        response.headers['WWW-Authenticate'] = 'Basic realm="Homefoil"'
    return response, status

auth_blueprint = Blueprint('auth', __name__)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

# What a session still on the default password may reach: the pages to change it or leave.
PASSWORD_CHANGE_ENDPOINTS = {'auth.change_password', 'auth.login', 'auth.logout', 'static', 'webmanifest'}

@auth_blueprint.before_app_request
def require_password_change():
    """Send a web session on the default password to change it. Shop clients use Basic Auth, never the session."""
    if (request.endpoint in PASSWORD_CHANGE_ENDPOINTS or not current_user.is_authenticated
            or not is_default_password(current_user.password)):
        return None
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'error': 'The default password must be changed first.'}), 403
    return redirect(url_for('auth.change_password', next=request.path))

def create_or_update_user(username, password, admin_access=False, shop_access=False, backup_access=False):
    """
    Create a new user or update an existing user with the given credentials and access rights.
    """
    # Validate username before creating/updating user
    is_valid, error_message = validate_username(username)
    if not is_valid:
        logger.error(f'Username validation failed for user {username}: {error_message}')
        raise ValueError(f"Username validation failed: {error_message}")
    
    # Validate password before creating/updating user
    is_valid, error_message = validate_password(password)
    if not is_valid:
        logger.error(f'Password validation failed for user {username}: {error_message}')
        raise ValueError(f"Password validation failed: {error_message}")
    
    user = User.query.filter_by(user=username).first()
    if user:
        logger.info(f'Updating existing user {username}')
        user.admin_access = admin_access
        user.shop_access = shop_access
        user.backup_access = backup_access
        user.password = generate_password_hash(password, method='scrypt')
    else:
        logger.info(f'Creating new user {username}')
        new_user = User(user=username, password=generate_password_hash(password, method='scrypt'), admin_access=admin_access, shop_access=shop_access, backup_access=backup_access)
        db.session.add(new_user)
    db.session.commit()

def init_user_from_environment(environment_name, admin=False):
    """
    allow to init some user from environment variable to init some users without using the UI
    """
    username = os.getenv(environment_name + '_NAME')
    password = os.getenv(environment_name + '_PASSWORD')
    if username and password:
        if admin:
            logger.info('Initializing an admin user from environment variable...')
            admin_access = True
            shop_access = True
            backup_access = True
        else:
            logger.info('Initializing a regular user from environment variable...')
            admin_access = False
            shop_access = True
            backup_access = False

        if not admin:
            existing_admin = admin_account_created()
            if not existing_admin and not admin_access:
                logger.error(f'Error creating user {username}, first account created must be admin')
                return

        create_or_update_user(username, password, admin_access, shop_access, backup_access)

def init_users(app):
    with app.app_context():
        # init users from ENV
        if os.environ.get('USER_ADMIN_NAME') is not None:
            init_user_from_environment(environment_name="USER_ADMIN", admin=True)
        if os.environ.get('USER_GUEST_NAME') is not None:
            init_user_from_environment(environment_name="USER_GUEST", admin=False)
        if User.query.first() is None:
            # Not create_or_update_user: validate_password is for the passwords people choose.
            db.session.add(User(user=DEFAULT_ADMIN, password=generate_password_hash(DEFAULT_PASSWORD, method='scrypt'),
                                admin_access=True, shop_access=True, backup_access=True))
            db.session.commit()
            logger.warning(f'No user accounts: created the default admin account {DEFAULT_ADMIN}/{DEFAULT_PASSWORD}, '
                           'its password must be changed at the first login.')

def local_url(url):
    """url if it is a path on this server, else '/': `next` must not send a login elsewhere."""
    # Browsers drop tabs and newlines from a URL, so '/\t/evil.com' would read as '//evil.com'.
    url = re.sub(r'[\t\r\n]', '', url)
    return url if url.startswith('/') and not url.startswith(('//', '/\\')) else '/'

@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        next_url = request.args.get('next', '')
        if current_user.is_authenticated:
            return redirect(local_url(next_url))
        admin = User.query.filter_by(user=DEFAULT_ADMIN).first()
        return render_template('login.html', title='Login',
                               default_password_active=bool(admin and is_default_password(admin.password)))
        
    # login code goes here
    username = request.form.get('user')
    password = request.form.get('password')
    remember = bool(request.form.get('remember'))
    next_url = request.form.get('next', '')

    user = check_credentials(username, password)
    if not user:
        logger.warning(f'Incorrect login for user {username}')
        return redirect(url_for('auth.login', failed=1, next=next_url or None))

    # if the above check passes, then we know the user has the right credentials
    logger.info(f'Sucessfull login for user {username}')
    login_user(user, remember=remember)

    if password == DEFAULT_PASSWORD:
        return redirect(url_for('auth.change_password', next=next_url or None))
    return redirect(local_url(next_url))

@auth_blueprint.route('/password', methods=['GET', 'POST'])
@login_required
def change_password():
    next_url = request.values.get('next', '')
    forced = is_default_password(current_user.password)
    error = None
    if request.method == 'POST':
        new_password = request.form.get('password', '')
        valid, error = validate_password(new_password)
        # The default password is public, so only a voluntary change asks for the current one.
        if not forced and not verify_password(current_user.password, request.form.get('current', '')):
            error = 'Your current password is wrong.'
        elif new_password != request.form.get('confirm'):
            error = 'The passwords do not match.'
        elif new_password == DEFAULT_PASSWORD:
            error = 'Choose a password other than the default one.'
        elif valid:
            user = current_user._get_current_object()
            user.password = generate_password_hash(new_password, method='scrypt')
            db.session.commit()
            # User.get_id() carries a hash fragment, so the session (and any remember cookie) is reissued.
            login_user(user, remember=COOKIE_NAME in request.cookies)
            logger.info(f'Password changed for user {user.user}')
            return redirect(local_url(next_url))
    return render_template('password.html', title='Change password', forced=forced, next=next_url,
                           back=local_url(next_url), error=error)

@auth_blueprint.route('/profile')
@login_required
@access_required('backup')
def profile():
    return render_template('profile.html')

@auth_blueprint.route('/api/users')
@access_required('admin')
def get_users():
    all_users = [
        dict(db_user._mapping)
        for db_user in db.session.query(User.id, User.user, User.admin_access, User.shop_access, User.backup_access).all()
    ]
    return jsonify(all_users)

@auth_blueprint.route('/api/user', methods=['DELETE'])
@login_required
@access_required('admin')
def delete_user():
    success = True
    data = request.json
    user_id = data['user_id']
    user = User.query.filter_by(id=user_id).first()
    if user and user.admin_access and admin_account_created() == 1:
        # With no admin left, authentication switches off for everyone.
        return jsonify({'success': False, 'error': 'Cannot delete the last admin account.'})
    try:
        User.query.filter_by(id=user_id).delete()
        db.session.commit()
        logger.info(f'Successfully deleted user with id {user_id}.')
    except Exception as e:
        logger.error(f'Could not delete user with id {user_id}: {e}')
        success = False

    resp = {
        'success': success
    } 
    return jsonify(resp)

@auth_blueprint.route('/api/user/signup', methods=['POST'])
@access_required('admin')
def signup_post():
    signup_success = True
    data = request.json

    username = data['user']
    password = data['password']
    admin_access = data['admin_access']
    if admin_access:
        shop_access = True
        backup_access = True
    else:
        shop_access = data['shop_access']
        backup_access = data['backup_access']

    # Validate username first
    is_valid, error_message = validate_username(username)
    if not is_valid:
        logger.error(f'Username validation failed for user {username}: {error_message}')
        resp = {
            'success': False,
            'error': f"Username validation failed: {error_message}"
        }
        return jsonify(resp)

    # Validate password
    is_valid, error_message = validate_password(password)
    if not is_valid:
        logger.error(f'Password validation failed for user {username}: {error_message}')
        resp = {
            'success': False,
            'error': f"Password validation failed: {error_message}"
        }
        return jsonify(resp)

    user = User.query.filter_by(user=username).first() # if this returns a user, then the user already exists in database
    
    if user: # if a user is found, we want to redirect back to signup page so user can try again
        logger.error(f'Error creating user {username}, user already exists')
        resp = {
            'success': False,
            'error': 'User already exists'
        }
        return jsonify(resp)
    
    existing_admin = admin_account_created()
    if not existing_admin and not admin_access:
        logger.error(f'Error creating user {username}, first account created must be admin')
        resp = {
            'success': False,
            'status_code': 400,
            'location': '/admin/settings',
        } 
        return jsonify(resp)

    try:
        # create a new user with the form data. Hash the password so the plaintext version isn't saved.
        create_or_update_user(username, password, admin_access, shop_access, backup_access)
        logger.info(f'Successfully created user {username}.')
    except ValueError as e:
        # This should not happen since we validate above, but just in case
        resp = {
            'success': False,
            'error': str(e)
        }
        return jsonify(resp)

    resp = {
        'success': signup_success
    } 

    if not existing_admin and admin_access:
        logger.debug('First admin account created')
        resp['status_code'] = 302,
        resp['location'] = '/admin/settings'
    
    return jsonify(resp)


@auth_blueprint.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')