#include <metal_stdlib>
using namespace metal;

struct GlassUniforms {
    float4 res;       // x: width, y: height, z: time, w: aspect
    float4 themeA;    // rgb: highlight, w: cursor_x
    float4 themeB;    // rgb: accent, w: cursor_y
    float4 themeC;    // rgb: reflection, w: opacity
    float4 bezel;     // x: margin, y: radius, z: premultiplied, w: close_btn
    float4 panel0;    // x, y, w, h
    float4 panel1;    // x, y, w, h
};

struct VertexInput {
    float2 position [[attribute(0)]];
    float2 uv [[attribute(1)]];
};

struct VertexOutput {
    float4 position [[position]];
    float2 uv;
};

// Simple pseudo-random hash for liquid caustics
inline float hash21(float2 p) {
    p = fract(p * float2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// Rounded-rectangle distance field
inline float sdRoundRect(float2 p, float2 b, float r) {
    float2 d = abs(p) - b + float2(r);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
}

vertex VertexOutput liquid_glass_vertex(
    uint vertexID [[vertex_id]],
    constant float2 *positions [[buffer(0)]],
    constant float2 *uvs [[buffer(1)]]
) {
    VertexOutput out;
    out.position = float4(positions[vertexID], 0.0, 1.0);
    out.uv = uvs[vertexID];
    return out;
}

fragment float4 liquid_glass_fragment(
    VertexOutput in [[stage_in]],
    constant GlassUniforms &u [[buffer(0)]]
) {
    float2 frag = in.position.xy;
    float2 uv = frag / max(u.res.xy, float2(1.0, 1.0));
    float2 halfRes = u.res.xy * 0.5;
    float r = max(u.bezel.y, 16.0);
    float outer = sdRoundRect(frag - halfRes, halfRes, r);

    // Inner panel boxes
    float p0 = sdRoundRect((frag - (u.panel0.xy + u.panel0.zw * 0.5)), u.panel0.zw * 0.5, 12.0);
    float p1 = sdRoundRect((frag - (u.panel1.xy + u.panel1.zw * 0.5)), u.panel1.zw * 0.5, 12.0);
    float panelDist = min(p0, p1);
    float panel = 1.0 - smoothstep(-2.0, 0.5, panelDist);
    float panelLip = smoothstep(1.5, -0.5, abs(panelDist) - 0.7);

    // Bezel slopes and light-catching rims
    float rimSlope = smoothstep(0.0, -u.bezel.x, outer);
    float large = smoothstep(0.5, -3.5, outer);
    float shoulder = smoothstep(-1.0, -8.0, outer) - smoothstep(-8.0, -18.0, outer);
    float echo = smoothstep(-7.0, -14.0, outer) - smoothstep(-14.0, -26.0, outer);
    float echoFar = smoothstep(-18.0, -28.0, outer) - smoothstep(-28.0, -42.0, outer);
    float toe = smoothstep(-u.bezel.x + 10.0, -u.bezel.x, outer);
    float hair = smoothstep(0.3, -0.4, abs(outer + 0.3));
    float bead = smoothstep(1.2, -0.2, abs(outer + 2.4));
    float glint = smoothstep(1.5, -0.5, abs(outer + 4.8)) * (1.0 - uv.y * 0.6);

    // Refractive theme mixing (Highlight, Accent, Reflection)
    float3 hi = u.themeA.rgb;
    float3 accent = u.themeB.rgb;
    float3 refl = u.themeC.rgb;
    float3 theme = mix(hi, accent, 0.42);
    theme = mix(theme, refl, 0.20);

    // Caustics & still water body
    float caust = hash21(floor(frag * 0.12) + u.res.z * 0.05);
    float caustFine = hash21(floor(frag * 0.24) - u.res.z * 0.08);
    float3 water = float3(0.92, 0.94, 0.98);
    water = mix(water, theme, 0.22);
    water += theme * (caust * 0.16 + caustFine * 0.08);

    // Panel well shading
    float3 panelCol = mix(float3(0.34, 0.36, 0.44), theme, 0.34);
    water = mix(water, panelCol, panel * 0.45);
    water += mix(float3(1.0), theme, 0.45) * panelLip * 0.22;

    // Outer rim refraction & sloped glass highlights
    float3 col = water;
    col = mix(col, mix(float3(1.0), theme, 0.28), large * 0.80);
    col = mix(col, mix(theme, float3(1.0), 0.25), shoulder * 0.55);
    col += mix(theme, float3(1.0), 0.35) * echo * 0.16;
    col += theme * echoFar * 0.08;
    col = mix(col, col * float3(0.72, 0.76, 0.84), toe * 0.65);
    col = mix(col, float3(1.0), hair);
    col = mix(col, mix(float3(1.0), theme, 0.15), bead * 0.9);
    col += float3(1.0) * glint * 0.75;

    // Specular highlight from mouse cursor position
    float2 m = float2(u.themeA.w, u.themeB.w);
    float2 lp = (m - uv) * float2(max(u.res.w, 0.5), 1.0);
    float spec = pow(max(0.0, 1.0 - length(lp) * 1.8), 8.0);
    col += float3(1.0) * spec * 0.28 * large;

    // Close button badge (top right)
    if (u.bezel.w > 0.5) {
        float margin = max(u.bezel.x, 8.0);
        float2 cpos = float2(u.res.x - margin * 0.72, margin * 0.62);
        float cd = length(frag - cpos);
        float cr = margin * 0.30;
        float disc = smoothstep(cr + 0.8, cr - 1.2, cd);
        float3 discCol = mix(float3(0.98, 0.985, 1.0), theme, 0.06);
        col = mix(col, discCol, disc);
        float ring = (1.0 - smoothstep(0.15, 1.6, abs(cd - (cr - 1.0)))) * disc;
        col = mix(col, float3(1.0), ring);
        float xmark = min(
            smoothstep(4.2, 1.3, abs((frag.x - cpos.x) - (frag.y - cpos.y))),
            smoothstep(4.2, 1.3, abs((frag.x - cpos.x) + (frag.y - cpos.y)))
        );
        xmark *= smoothstep(cr * 0.58, cr * 0.20, cd);
        col = mix(col, float3(0.02, 0.02, 0.025), xmark);
    }

    // Alpha with 10% core transparency reduction and dynamic breathing modulation
    float alpha = 0.50 * (1.0 - panel * 0.25);
    if (u.themeC.w > 0.0) {
        alpha *= u.themeC.w;
    }
    alpha *= smoothstep(0.8, -0.4, outer);

    float3 rgb = clamp(col, 0.0, 1.0);
    if (u.bezel.z > 0.5) {
        return float4(rgb * alpha, alpha);
    } else {
        return float4(rgb, 1.0);
    }
}
