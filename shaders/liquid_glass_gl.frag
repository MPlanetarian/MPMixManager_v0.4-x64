#version 330 core

// Still water held in clear glass (OpenGL Core 3.3+).
// Supports AMD Radeon, Intel, NVIDIA, and older OpenGL-capable GPUs.
// The colour of the player's theme sits in the water and does not move.
// The rim is a slope, so the same edge throws a broad reflection and smaller ones.
// Darker glass panels sit where the player draws its boxed panels.
// KWin fades the whole pane; brighter pixels read as the lit slope, darker pixels as the shaded panels.

in vec2 vUv;
out vec4 outColor;

uniform vec4 u_res;     // width, height, time (unused; the water is still), aspect
uniform vec4 u_themeA;  // highlight rgb, mouse x
uniform vec4 u_themeB;  // accent rgb, mouse y
uniform vec4 u_themeC;  // second reflection rgb, opacity hint
uniform vec4 u_bezel;   // margin px, corner radius, premul (1/0), close-button flag
uniform vec4 u_panel0;  // x, y, width, height in framebuffer pixels
uniform vec4 u_panel1;

struct GlassUBO_t {
    vec4 res;
    vec4 themeA;
    vec4 themeB;
    vec4 themeC;
    vec4 bezel;
    vec4 panel0;
    vec4 panel1;
};

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p = p * 2.03 + vec2(1.7, 9.2);
        a *= 0.5;
    }
    return v;
}

float sdRoundRect(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float panelMask(vec2 frag, vec4 r) {
    if (r.z < 4.0 || r.w < 4.0) {
        return 0.0;
    }
    vec2 halfSize = 0.5 * r.zw;
    float rad = clamp(min(halfSize.x, halfSize.y) * 0.18, 8.0, 22.0);
    float d = sdRoundRect(frag - (r.xy + halfSize), halfSize, rad);
    float body = 1.0 - smoothstep(-0.5, 1.5, d);
    return body;
}

void main() {
    GlassUBO_t u = GlassUBO_t(u_res, u_themeA, u_themeB, u_themeC, u_bezel, u_panel0, u_panel1);

    vec2 frag = vUv * u.res.xy;
    vec2 center = 0.5 * u.res.xy;
    vec2 p = frag - center;
    float rad = u.bezel.y;

    vec2 halfSize = center - vec2(1.0);
    float outer = sdRoundRect(p, halfSize, rad);
    if (outer > 0.6) {
        outColor = vec4(0.0);
        return;
    }

    vec3 hi = u.themeA.rgb;
    vec3 accent = u.themeB.rgb;
    vec3 refl = u.themeC.rgb;
    vec3 theme = mix(hi, accent, 0.42);
    theme = mix(theme, refl, 0.20);

    // Frozen water. The pattern is tied to the glass, not to time.
    vec2 uv = frag / u.res.xy;
    float n = fbm(uv * 4.6);
    float n2 = fbm(uv * 9.5 + vec2(3.1, 8.4));
    float caust = smoothstep(0.58, 0.86, n);
    float caustFine = smoothstep(0.74, 0.92, n2);

    vec3 water = vec3(0.76, 0.80, 0.87);
    water = mix(water, theme, 0.22);
    water += theme * (caust * 0.16 + caustFine * 0.08);
    water += vec3(0.95, 0.97, 1.0) * caustFine * 0.04;

    float title = panelMask(frag, u.panel0);
    float library = panelMask(frag, u.panel1);
    float panel = max(title, library);
    vec3 panelCol = mix(vec3(0.34, 0.36, 0.44), theme, 0.34);
    // A short slope around each panel, lighter on the lip and darker inside.
    water = mix(water, panelCol, panel * 0.82);
    float panelLip = 0.0;
    if (u.panel0.z > 4.0) {
        vec2 h0 = 0.5 * u.panel0.zw;
        float d0 = sdRoundRect(frag - (u.panel0.xy + h0), h0, 14.0);
        panelLip = max(panelLip, exp(-pow((abs(d0) - 1.5) / 2.2, 2.0)));
    }
    if (u.panel1.z > 4.0) {
        vec2 h1 = 0.5 * u.panel1.zw;
        float d1 = sdRoundRect(frag - (u.panel1.xy + h1), h1, 16.0);
        panelLip = max(panelLip, exp(-pow((abs(d1) - 1.5) / 2.4, 2.0)));
    }
    water += mix(vec3(1.0), theme, 0.45) * panelLip * 0.22;

    // Sloped outer edge. Distance across the bevel changes what it reflects.
    float edge = max(-outer, 0.0);
    float large = exp(-pow((edge - 6.5) / 5.0, 2.0));
    float shoulder = exp(-pow((edge - 16.0) / 4.2, 2.0));
    float echo = exp(-pow((edge - 46.0) / 9.0, 2.0));
    float echoFar = exp(-pow((edge - 84.0) / 7.0, 2.0));
    float hair = 1.0 - smoothstep(0.15, 2.0, edge);
    float toe = smoothstep(20.0, 28.0, edge) * (1.0 - smoothstep(28.0, 36.0, edge));

    vec2 beadCell = floor(frag / 6.5);
    float bead = step(0.84, hash(beadCell)) * step(edge, 24.0) * step(2.0, edge);
    float glint = step(0.94, hash(floor(frag / 3.0) + vec2(4.0, 1.0))) * step(edge, 12.0) * step(1.0, edge);

    vec3 col = water;
    col = mix(col, mix(vec3(1.0), theme, 0.28), large * 0.80);
    col = mix(col, mix(theme, vec3(1.0), 0.25), shoulder * 0.55);
    col += mix(theme, vec3(1.0), 0.35) * echo * 0.16;
    col += theme * echoFar * 0.08;
    col = mix(col, col * vec3(0.72, 0.76, 0.84), toe * 0.65);
    col = mix(col, vec3(1.0), hair);
    col = mix(col, mix(vec3(1.0), theme, 0.15), bead * 0.9);
    col += vec3(1.0) * glint * 0.75;

    vec2 m = vec2(u.themeA.w, u.themeB.w);
    vec2 lp = (m - uv) * vec2(max(u.res.w, 0.5), 1.0);
    float spec = pow(max(0.0, 1.0 - length(lp) * 1.8), 8.0);
    col += vec3(1.0) * spec * 0.28 * large;

    if (u.bezel.w > 0.5) {
        float margin = max(u.bezel.x, 8.0);
        vec2 cpos = vec2(u.res.x - margin * 0.72, margin * 0.62);
        float cd = length(frag - cpos);
        float cr = margin * 0.30;
        float disc = smoothstep(cr + 0.8, cr - 1.2, cd);
        vec3 discCol = mix(vec3(0.98, 0.985, 1.0), theme, 0.06);
        col = mix(col, discCol, disc);
        float ring = (1.0 - smoothstep(0.15, 1.6, abs(cd - (cr - 1.0)))) * disc;
        col = mix(col, vec3(1.0), ring);
        float xmark = min(
            smoothstep(4.2, 1.3, abs((frag.x - cpos.x) - (frag.y - cpos.y))),
            smoothstep(4.2, 1.3, abs((frag.x - cpos.x) + (frag.y - cpos.y)))
        );
        xmark *= smoothstep(cr * 0.58, cr * 0.20, cd);
        col = mix(col, vec3(0.02, 0.02, 0.025), xmark);
    }

    float alpha = 0.50 * (1.0 - panel * 0.25);
    if (u.themeC.w > 0.0) {
        alpha *= u.themeC.w;
    }
    alpha *= smoothstep(0.8, -0.4, outer);
    vec3 rgb = clamp(col, 0.0, 1.0);
    if (u.bezel.z > 0.5) {
        outColor = vec4(rgb * alpha, alpha);
    } else {
        outColor = vec4(rgb, 1.0);
    }
}
