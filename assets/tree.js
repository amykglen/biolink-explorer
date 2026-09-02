// D3 renderer for the Biolink Explorer.
//
// Left-to-right hierarchy drawn as small circle nodes with the label beside each
// circle — to the LEFT for internal nodes (which have children on the right) and to
// the RIGHT for leaf nodes — the classic tidy-tree convention. Links are smooth
// horizontal-bump curves (d3.curveBumpX). Labels get a background-colored halo so
// they stay legible where they cross a link.
//
// Layout adapts to the data:
//   * pure tree (mixins hidden) -> d3.tree, with columns spaced to fit the labels
//     that stick out of each side,
//   * DAG (mixins shown, multiple parents) -> dagre layered layout, so every node
//     sits in its true depth column.
//
// Data in: the Cytoscape-style element list Dash already produces
//   nodes: {data:{id,label,attributes}, classes:"canonical mixin ..."}
//   edges: {data:{source,target}}
// Click out: dash_clientside.set_props(selectedStoreId, {data:[nodeData]}).

(function () {
    // Palette — kept in sync with styles.py (node colors: teal regular, gold mixin)
    var P = {
        bg: "#f8f7f4",
        text: "#2a2825",
        regular: "#2d8f83",      // regular nodes (teal)
        regular_dark: "#1f6d64",
        mixin: "#bd901f",        // mixin nodes (gold)
        mixin_dark: "#93701a",
        highlight: "#c0562f",    // searched (rust)
        edge: "#dad6cf",
    };
    var FONT_FAMILY = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
    var FONT_SIZE = 14, FONT_WEIGHT = 500;
    var FONT = FONT_WEIGHT + " " + FONT_SIZE + "px " + FONT_FAMILY;

    // Geometry
    var R = 4.5;            // circle radius
    var LABEL_GAP = 7;      // gap between circle and its label
    var MIN_COL_GAP = 28;   // minimum horizontal gap between adjacent column labels
    var FIT_PAD = 28;
    var MIN_OPEN_ZOOM = 0.85;  // fallback (big graphs): don't open more zoomed-out than this
    var FIT_FULL_MIN = 0.28;   // if the whole graph fits at >= this zoom, open showing all of it
    var DAGRE = { ranksep: 78, edgesep: 6 };

    // Vertical spacing scales with node count: tight for big graphs, airier when a
    // filter/search narrows the graph to just a few nodes.
    function rowSpacing(n) {
        var minRow = 16, maxRow = 31, nMin = 6, nMax = 95;
        if (n <= nMin) return maxRow;
        if (n >= nMax) return minRow;
        return maxRow + (minRow - maxRow) * (n - nMin) / (nMax - nMin);
    }

    var _ctx = document.createElement("canvas").getContext("2d");
    function textWidth(s) { _ctx.font = FONT; return _ctx.measureText(s).width; }
    function classesOf(el) { return (el.classes || "").split(/\s+/).filter(Boolean); }

    var linkGen = d3.line().x(function (d) { return d[0]; }).y(function (d) { return d[1]; }).curve(d3.curveBumpX);

    // Visual encoding (all nodes are circles):
    //   color -> mixin-ness    (green = regular, gold = mixin; both tabs)
    //   fill  -> canonical-ness (solid = canonical / any category, hollow = non-canonical predicate)
    // Domain/range specificity is intentionally not encoded on the node.
    function nodeStyle(classes, selected) {
        var has = function (c) { return classes.indexOf(c) >= 0; };
        var mixin = has("mixin");
        var color = mixin ? P.mixin : P.regular;
        var s = { fill: color, stroke: color, sw: 1.5, r: R, text: P.text, ring: false, searchRing: false };
        if (has("noncanonical")) { s.fill = "none"; s.sw = 1.75; }  // hollow
        if (has("searched")) {
            // A search match must NOT recolor the dot — its color (mixin) and fill
            // (canonical) both carry meaning. Mark it with an outer rust ring + a rust,
            // bold label, so matches pop without overriding the encoding.
            s.searchRing = true;
            s.text = P.highlight;
        }
        if (selected) {
            // Likewise don't touch the fill — enlarge, thicken the stroke, add a ring.
            s.sw = s.sw + 0.75; s.r = s.r + 2.5; s.ring = true;
            if (!s.searchRing) s.text = mixin ? P.mixin_dark : P.regular_dark;
        }
        return s;
    }

    // ---- Tree layout ----
    function treeLayout(info, adj, roots, ROW) {
        var visited = {}, treeChildren = {}, queue = [];
        roots.forEach(function (r) { visited[r] = true; queue.push(r); });
        while (queue.length) {
            var u = queue.shift();
            (adj[u] || []).forEach(function (v) {
                if (!visited[v]) { visited[v] = true; (treeChildren[u] || (treeChildren[u] = [])).push(v); queue.push(v); }
            });
        }
        Object.keys(info).forEach(function (id) { if (!visited[id]) { visited[id] = true; roots.push(id); } });

        function build(id) { return { id: id, children: (treeChildren[id] || []).map(build) }; }
        var hierarchy = d3.hierarchy({ id: "__virtual__", children: roots.map(build) });
        d3.tree().nodeSize([ROW, 1]).separation(function (a, b) { return a.parent === b.parent ? 1 : 1.25; })(hierarchy);

        // Per-depth label extents: internal labels stick out left, leaf labels stick out right.
        var leftExt = {}, rightExt = {}, maxDepth = 0;
        hierarchy.each(function (d) {
            if (d.data.id === "__virtual__") return;
            var it = info[d.data.id];
            it.internal = !!(adj[d.data.id] && adj[d.data.id].length);
            if (it.internal) leftExt[d.depth] = Math.max(leftExt[d.depth] || 0, it.labelW);
            else rightExt[d.depth] = Math.max(rightExt[d.depth] || 0, it.labelW);
            if (d.depth > maxDepth) maxDepth = d.depth;
        });
        var colX = { 1: 0 };
        for (var depth = 2; depth <= maxDepth; depth++) {
            var gap = (R + LABEL_GAP + (rightExt[depth - 1] || 0)) + MIN_COL_GAP + ((leftExt[depth] || 0) + LABEL_GAP + R);
            colX[depth] = colX[depth - 1] + gap;
        }
        var pos = {};
        hierarchy.each(function (d) {
            if (d.data.id === "__virtual__") return;
            pos[d.data.id] = { cx: colX[d.depth], cy: d.x, internal: info[d.data.id].internal, labelW: info[d.data.id].labelW };
        });
        return { pos: pos };
    }

    // ---- DAG layout (dagre) ----
    function dagreLayout(info, validEdges, adj, ROW) {
        var nodesep = Math.max(6, ROW - 16);
        var gr = new dagre.graphlib.Graph({ directed: true });
        gr.setGraph({ rankdir: "LR", ranksep: DAGRE.ranksep, nodesep: nodesep, edgesep: DAGRE.edgesep, marginx: FIT_PAD, marginy: FIT_PAD });
        gr.setDefaultEdgeLabel(function () { return {}; });
        Object.keys(info).forEach(function (id) {
            var internal = !!(adj[id] && adj[id].length);
            gr.setNode(id, { width: 2 * R + LABEL_GAP + info[id].labelW, height: 16, internal: internal });
        });
        validEdges.forEach(function (e) { gr.setEdge(e.data.source, e.data.target); });
        dagre.layout(gr);

        // dagre aligns node-box CENTERS per rank; since each box's width includes its
        // side label, the circles (dots) would land at different x within a rank. We take
        // only dagre's vertical resolution (n.y) + its rank assignment, then recompute a
        // single dot-column x per rank — internal labels extend left, leaf labels right,
        // the same spacing model the tree layout uses — so every dot in a rank lines up.
        // dagre gives all nodes in a rank the same box-center x; bucket by that x to rank.
        var rankXs = [];
        gr.nodes().forEach(function (id) {
            var x = gr.node(id).x, hit = false;
            for (var i = 0; i < rankXs.length; i++) { if (Math.abs(rankXs[i] - x) < 2) { hit = true; break; } }
            if (!hit) rankXs.push(x);
        });
        rankXs.sort(function (a, b) { return a - b; });
        function rankOf(x) { for (var i = 0; i < rankXs.length; i++) if (Math.abs(rankXs[i] - x) < 2) return i; return 0; }

        var leftExt = {}, rightExt = {};
        gr.nodes().forEach(function (id) {
            var n = gr.node(id), r = rankOf(n.x);
            if (n.internal) leftExt[r] = Math.max(leftExt[r] || 0, info[id].labelW);
            else rightExt[r] = Math.max(rightExt[r] || 0, info[id].labelW);
        });
        var colX = { 0: 0 };
        for (var d = 1; d < rankXs.length; d++) {
            colX[d] = colX[d - 1] + (R + LABEL_GAP + (rightExt[d - 1] || 0)) + MIN_COL_GAP + ((leftExt[d] || 0) + LABEL_GAP + R);
        }

        var pos = {};
        gr.nodes().forEach(function (id) {
            var n = gr.node(id), r = rankOf(n.x);
            pos[id] = { cx: colX[r], cy: n.y, internal: n.internal, labelW: info[id].labelW };
        });
        // Return no routed points -> edges draw as clean bump curves between dots
        // (dagre's own routing produced squiggles once we moved the dots).
        return { pos: pos, points: {} };
    }

    function render(containerId, elements, opts) {
        opts = opts || {};
        var container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = "";
        if (!elements || !elements.length) return;

        var nodes = [], edges = [];
        elements.forEach(function (e) {
            if (!e || !e.data) return;
            if (e.data.source !== undefined) edges.push(e);
            else if (e.data.id !== undefined) nodes.push(e);
        });
        if (!nodes.length) return;

        var info = {};
        nodes.forEach(function (n) {
            var label = n.data.label != null ? n.data.label : n.data.id;
            info[n.data.id] = { id: n.data.id, label: label, classes: classesOf(n), data: n.data, labelW: textWidth(label) };
        });
        var validEdges = edges.filter(function (e) { return info[e.data.source] && info[e.data.target]; });

        var indeg = {}, adj = {};
        Object.keys(info).forEach(function (id) { indeg[id] = 0; });
        validEdges.forEach(function (e) { indeg[e.data.target]++; (adj[e.data.source] || (adj[e.data.source] = [])).push(e.data.target); });
        var roots = Object.keys(info).filter(function (id) { return indeg[id] === 0; });
        if (!roots.length) roots = [nodes[0].data.id];

        var isDag = Object.keys(info).some(function (id) { return indeg[id] > 1; }) && window.dagre;

        var ROW = rowSpacing(Object.keys(info).length);
        var pos, edgePoints = {};
        if (isDag) { var o = dagreLayout(info, validEdges, adj, ROW); pos = o.pos; edgePoints = o.points; }
        else { pos = treeLayout(info, adj, roots.slice(), ROW).pos; }

        function pointsFor(e) {
            var s = pos[e.data.source], t = pos[e.data.target];
            if (!s || !t) return null;
            var key = e.data.source + " " + e.data.target;
            if (edgePoints[key]) {
                var pts = edgePoints[key].slice();
                pts[0] = [s.cx, s.cy]; pts[pts.length - 1] = [t.cx, t.cy];
                return pts;
            }
            return [[s.cx, s.cy], [t.cx, t.cy]];
        }

        // Bounds (include the label that sticks out of each circle)
        var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        Object.keys(pos).forEach(function (id) {
            var p = pos[id];
            var x0 = p.internal ? (p.cx - R - LABEL_GAP - p.labelW) : (p.cx - R);
            var x1 = p.internal ? (p.cx + R) : (p.cx + R + LABEL_GAP + p.labelW);
            minX = Math.min(minX, x0); maxX = Math.max(maxX, x1);
            minY = Math.min(minY, p.cy - 10); maxY = Math.max(maxY, p.cy + 10);
        });
        var rootCy = pos[roots[0]] ? pos[roots[0]].cy : (minY + maxY) / 2;
        var gW = (maxX - minX) || 1, gH = (maxY - minY) || 1;

        // --- SVG ---
        var svg = d3.select(container).append("svg")
            .attr("width", "100%").attr("height", "100%")
            .style("display", "block").style("background", P.bg).style("cursor", "grab");
        var g = svg.append("g");

        // Links
        var linkLayer = g.append("g");
        validEdges.forEach(function (e) {
            var pts = pointsFor(e);
            if (pts) linkLayer.append("path").attr("d", linkGen(pts)).attr("fill", "none").attr("stroke", P.edge).attr("stroke-width", 1.25);
        });

        // Nodes (circle + side label)
        var nodeLayer = g.append("g");
        var current = { state: null, paint: null };  // the selected node
        Object.keys(pos).forEach(function (id) {
            var it = info[id]; if (!it) return;
            var p = pos[id], internal = p.internal;
            var base = nodeStyle(it.classes, false);
            var state = { sel: false, hover: false };
            var ng = nodeLayer.append("g").attr("transform", "translate(" + p.cx + "," + p.cy + ")")
                .style("cursor", "pointer");
            var searchRing = ng.append("circle").attr("fill", "none").attr("stroke", P.highlight)
                .attr("stroke-width", 1.75).attr("opacity", 0.95).attr("r", 0);  // search-match ring
            var ring = ng.append("circle").attr("fill", "none").attr("stroke", P.text)
                .attr("stroke-width", 1.25).attr("opacity", 0.55).attr("r", 0);  // selection ring
            var circle = ng.append("circle");
            var label = ng.append("text")
                .attr("y", 0).attr("text-anchor", internal ? "end" : "start").attr("dominant-baseline", "central")
                .attr("font-family", FONT_FAMILY).attr("font-size", FONT_SIZE)
                .attr("stroke", P.bg).attr("stroke-width", 4.5).attr("paint-order", "stroke")  // legibility halo
                .attr("pointer-events", "none").text(it.label);
            // transparent hit area covering circle + label
            ng.append("rect")
                .attr("x", internal ? -(base.r + 3 + LABEL_GAP + it.labelW) : -(base.r + 3))
                .attr("y", -9).attr("width", (base.r + 3) * 2 + LABEL_GAP + it.labelW).attr("height", 18)
                .attr("fill", "transparent");

            function paint() {
                var s = nodeStyle(it.classes, state.sel);
                var r = s.r, weight = FONT_WEIGHT;
                if (state.hover && !state.sel) { r = s.r + 1.5; weight = 600; }
                if (state.sel) weight = 700;
                circle.attr("r", r).attr("fill", s.fill).attr("stroke", s.stroke).attr("stroke-width", s.sw);
                ring.attr("r", s.ring ? r + 3.5 : 0);
                searchRing.attr("r", s.searchRing ? r + 3 : 0);
                if (s.searchRing) weight = Math.max(weight, 700);  // bold rust label for matches
                var off = r + LABEL_GAP;
                label.attr("fill", s.text).attr("font-weight", weight).attr("x", internal ? -off : off);
            }
            paint();

            ng.on("mouseover", function () { state.hover = true; paint(); });
            ng.on("mouseout", function () { state.hover = false; paint(); });
            ng.on("click", function (event) {
                event.stopPropagation();
                if (current.state && current.state !== state) { current.state.sel = false; current.paint(); }
                state.sel = true; current.state = state; current.paint = paint; paint();
                if (opts.selectedStoreId && window.dash_clientside && window.dash_clientside.set_props) {
                    window.dash_clientside.set_props(opts.selectedStoreId, { data: [it.data] });
                }
            });
        });

        // --- Zoom / initial view ---
        var didPan = false;
        var zoom = d3.zoom().scaleExtent([0.08, 4])
            .extent(function () { return [[0, 0], [container.clientWidth || 1, container.clientHeight || 1]]; })
            .on("start", function () {
                didPan = false;
                // Any interaction with the graph should dismiss an open dropdown. d3.zoom
                // stops the real mousedown from reaching the document, so dropdowns (which
                // close on an outside mousedown) never see it — dispatch a synthetic one.
                document.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
                if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
            })
            .on("zoom", function (event) {
                g.attr("transform", event.transform);
                if (event.sourceEvent && event.sourceEvent.type !== "wheel") didPan = true;
            });
        svg.call(zoom).on("dblclick.zoom", null);

        // Bulletproof dropdown dismissal: a capture-phase listener on the container fires
        // on ANY pointer press in the graph, before d3.zoom can stop the event, and
        // dispatches an outside mousedown so open dropdowns close. Added once per container.
        if (!container._ddCloseHooked) {
            container._ddCloseHooked = true;
            container.addEventListener("mousedown", function () {
                document.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
                if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
            }, true);
        }

        // Clicking empty graph area (not a node, not a pan) clears the selection.
        svg.on("click", function () {
            if (didPan) { didPan = false; return; }
            if (current.state) { current.state.sel = false; current.paint(); current.state = null; current.paint = null; }
            if (opts.selectedStoreId && window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props(opts.selectedStoreId, { data: null });
            }
        });

        function applyInitialView() {
            var W = container.clientWidth, H = container.clientHeight;
            if (!W || !H) return false;
            var kFitAll = Math.min((W - 2 * FIT_PAD) / gW, (H - 2 * FIT_PAD) / gH);
            // Prefer to open showing the WHOLE graph (width AND height) — this is the nice
            // default for the unfiltered trees and for filtered subgraphs. But once mixins /
            // non-canonical are shown the graph is far too tall to fit usefully, so below a
            // usable fit-zoom we fall back to filling the width, anchored on the root and
            // never more zoomed-out than MIN_OPEN_ZOOM. Never zoom in past 1.15.
            var k = (kFitAll >= FIT_FULL_MIN)
                ? Math.min(1.15, kFitAll)
                : Math.min(1.15, Math.max((W - 2 * FIT_PAD) / gW, MIN_OPEN_ZOOM));
            var tx = FIT_PAD - minX * k;
            var ty = (k * gH <= H - 2 * FIT_PAD) ? (H - k * gH) / 2 - minY * k : H / 2 - rootCy * k;
            svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
            return true;
        }
        if (!applyInitialView()) {
            var ro = new ResizeObserver(function () { if (applyInitialView()) ro.disconnect(); });
            ro.observe(container);
        }
    }

    window.BiolinkTree = { render: render };
})();
