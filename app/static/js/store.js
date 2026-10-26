/** Shared by the library and title pages. */

async function gqlFetch(query, variables) {
    const params = new URLSearchParams({query});
    if (variables) params.set('variables', JSON.stringify(variables));
    const r = await fetch('/api/graphql?' + params, {
        headers: {'Accept': 'application/json'},
        credentials: 'same-origin',
    });
    if (!r.ok) throw new Error(`GraphQL HTTP ${r.status}`);
    const body = await r.json();
    if (body.errors && body.errors.length) throw new Error(JSON.stringify(body.errors));
    return body.data;
}

// titledb carries every region's text; this keeps what an en-GB page can show.
const LATIN = /^[\p{Script=Latin}\p{N}\p{P}\p{Zs}\p{S}]+$/u;

const cleanName = name => (name || 'Unrecognized title').replace(/[™®]/g, '').replace(/\s{2,}/g, ' ').trim();

function playersLabel(p) {
    if (!p) return '';
    return p === '1' ? '1 player' : `${p.replace(/\s*[-~]\s*/, '–')} players`;
}
