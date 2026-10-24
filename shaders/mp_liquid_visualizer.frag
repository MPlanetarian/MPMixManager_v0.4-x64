#version 450

// =============================================================================
// MP_Liquid_Visualizer — Native Vulkan 3D Generative Audio-Reactive Shader
// Preset 1: "Cosmic Dreamworlds (Liquid)"
// Inspired exclusively by MPlanetarian - Cosmic Dreamworlds [Deluxe Edition]
// cover art (https://mplanetarian.bandcamp.com) and procedural 3D architectural
// bio-mechanical & liquid-glass motion principles.
// =============================================================================

layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 outColor;

layout(set = 0, binding = 0) uniform VisualizerUBO {
    vec4 res;     // x: width (1400), y: height (1400), z: accum_time, w: is_playing (1.0/0.0)
    vec4 audio0;  // x: sub_bass, y: bass, z: low_mid, w: mid
    vec4 audio1;  // x: high_mid, y: treble, z: air, w: rms_energy
    vec4 audio2;  // x: beat_pulse, y: bass_phase, z: mid_phase, w: high_phase
    vec4 bands0;  // 4 spectrum bands (0..3)
    vec4 bands1;  // 4 spectrum bands (4..7)
    vec4 bands2;  // 4 spectrum bands (8..11)
    vec4 bands3;  // 4 spectrum bands (12..15)
    vec4 preset;  // x: preset_id (0 = Cosmic Dreamworlds (Liquid)), y: pitch_factor, z: dyn_range, w: seed
} u;

layout(set = 0, binding = 1) uniform sampler2D uCoverTex;

const float PI = 3.14159265359;
const float TAU = 6.28318530718;

// --- Rotation & Math Helpers ---
mat2 rot2(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float hash21(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec3 hash33(vec3 p3) {
    p3 = fract(p3 * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yxz + 33.33);
    return fract((p3.xxy + p3.yxx) * p3.zyx);
}

float noise3(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(mix(hash11(dot(i + vec3(0,0,0), vec3(1,57,113))),
                hash11(dot(i + vec3(1,0,0), vec3(1,57,113))), f.x),
            mix(hash11(dot(i + vec3(0,1,0), vec3(1,57,113))),
                hash11(dot(i + vec3(1,1,0), vec3(1,57,113))), f.x), f.y),
        mix(mix(hash11(dot(i + vec3(0,0,1), vec3(1,57,113))),
                hash11(dot(i + vec3(1,0,1), vec3(1,57,113))), f.x),
            mix(hash11(dot(i + vec3(0,1,1), vec3(1,57,113))),
                hash11(dot(i + vec3(1,1,1), vec3(1,57,113))), f.x), f.y), f.z);
}

// Smooth Minimum for liquid metaball fusion
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / max(k, 0.0001), 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

// Signed Distance Primitives
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}

// Cosmic Dreamworlds (Liquid) Signature Palette
// Extracted directly from MPlanetarian - Cosmic Dreamworlds [Deluxe Edition] cover art
vec3 cosmicPalette(float t, vec2 uvHint) {
    vec3 colCobalt   = vec3(0.02, 0.14, 0.98); // Electric Ultramarine / Cobalt Blue
    vec3 colMagenta  = vec3(0.98, 0.04, 0.68); // Hyper Magenta / Neon Pink
    vec3 colLime     = vec3(0.05, 0.99, 0.25); // Acid Emerald / Cyber Lime
    vec3 colGold     = vec3(1.00, 0.92, 0.04); // Solar Gold / Yellow
    vec3 colCrimson  = vec3(0.98, 0.06, 0.12); // Planetary Ring Crimson Red
    vec3 colCyan     = vec3(0.00, 0.95, 1.00); // Crystalline Liquid Cyan

    float s = fract(t);
    vec3 procCol;
    if (s < 0.2) {
        procCol = mix(colCobalt, colMagenta, s * 5.0);
    } else if (s < 0.4) {
        procCol = mix(colMagenta, colCrimson, (s - 0.2) * 5.0);
    } else if (s < 0.6) {
        procCol = mix(colCrimson, colGold, (s - 0.4) * 5.0);
    } else if (s < 0.8) {
        procCol = mix(colGold, colLime, (s - 0.6) * 5.0);
    } else {
        procCol = mix(colLime, colCyan, (s - 0.8) * 5.0);
    }

    // Blend with actual sampled cover art texture so the preset is authentically rooted in the cover
    vec2 texUv = fract(uvHint * 0.35 + vec2(0.5));
    vec3 coverSample = texture(uCoverTex, texUv).rgb;
    // Boost saturation of cover sample
    float luma = dot(coverSample, vec3(0.299, 0.587, 0.114));
    coverSample = clamp(mix(vec3(luma), coverSample, 1.45), 0.0, 1.0);

    return mix(procCol, coverSample, 0.42);
}

// Orbital Void Reflux Signature Palette
// Extracted directly from Cover_WMI_V2.png cover art
vec3 orbitalVoidPalette(float t, vec2 uvHint) {
    vec3 colCyan      = vec3(0.00, 0.94, 1.00); // Electric Reflux Cyan (#00f0ff)
    vec3 colViolet    = vec3(0.61, 0.31, 0.87); // Deep Orbital Void Violet (#9d4edd)
    vec3 colMagenta   = vec3(1.00, 0.00, 0.50); // Radiant Nebula Flux Magenta (#ff007f)
    vec3 colGold      = vec3(1.00, 0.84, 0.12); // Accretion Flare Gold
    vec3 colIndigo    = vec3(0.15, 0.07, 0.38); // Deep Void Space Indigo
    vec3 colStarlight = vec3(0.85, 0.96, 1.00); // Pure Celestial Starlight

    float s = fract(t);
    vec3 procCol;
    if (s < 0.20) {
        procCol = mix(colIndigo, colViolet, s * 5.0);
    } else if (s < 0.40) {
        procCol = mix(colViolet, colMagenta, (s - 0.20) * 5.0);
    } else if (s < 0.60) {
        procCol = mix(colMagenta, colGold, (s - 0.40) * 5.0);
    } else if (s < 0.80) {
        procCol = mix(colGold, colCyan, (s - 0.60) * 5.0);
    } else {
        procCol = mix(colCyan, colStarlight, (s - 0.80) * 5.0);
    }

    vec2 texUv = fract(uvHint * 0.35 + vec2(0.5));
    vec3 coverSample = texture(uCoverTex, texUv).rgb;
    float luma = dot(coverSample, vec3(0.299, 0.587, 0.114));
    coverSample = clamp(mix(vec3(luma), coverSample, 1.55), 0.0, 1.0);

    return mix(procCol, coverSample, 0.46);
}

vec3 getPresetPalette(float t, vec2 uvHint) {
    if (u.preset.x > 0.5) {
        return orbitalVoidPalette(t, uvHint);
    }
    return cosmicPalette(t, uvHint);
}

// =============================================================================
// 3D Generative Scene Map
// Returns vec2(distance, material_id)
// Materials:
//   1.0 = Translucent Liquid Glass Planetary Orbs & Metaballs (Refractive Chrome/Glass)
//   2.0 = Incandescent Planetary Accretion Rings & Halo Arcs (Luminous Neon)
//   3.0 = Mycelial Liquid Tendril Conduits & Connecting Filaments (Organic Pulse)
//   4.0 = Kinetic Polyhedral Shards & Orbital Fins (Architectural Tech Shards)
// =============================================================================
vec2 mapScene(vec3 p) {
    float t = u.res.z;
    float subBass = u.audio0.x;
    float bass = u.audio0.y;
    float lowMid = u.audio0.z;
    float mid = u.audio0.w;
    float highMid = u.audio1.x;
    float treble = u.audio1.y;
    float rms = u.audio1.w;
    float beat = u.audio2.x;
    float bassPhase = u.audio2.y;
    float midPhase = u.audio2.z;
    float highPhase = u.audio2.w;

    if (u.preset.x > 0.5) {
        // --- PRESET 1: ORBITAL VOID REFLUX ---
        vec3 centerVoid = vec3(
            0.15 * sin(t * 0.31 + bassPhase * 0.20),
            0.10 * cos(t * 0.27 + midPhase * 0.15),
            0.0
        );
        float radCore = 0.78 + 0.18 * subBass + 0.09 * beat;
        float rippleVoid = 0.052 * (0.35 + bass * 1.45) * sin(p.x * 6.8 + bassPhase * 2.1) * cos(p.y * 6.8 - t * 2.2) * sin(p.z * 6.8 + highPhase);
        float dVoid = sdSphere(p - centerVoid, radCore) + rippleVoid;

        // Orbiting fluid satellites in elliptical reflux orbits (Liquid Metaballs)
        float dLiquid = dVoid;
        for (int i = 0; i < 6; i++) {
            float fi = float(i);
            float ang = t * (0.62 + fi * 0.12) + fi * 1.047 + bassPhase * 0.35;
            float elev = sin(t * (0.45 + fi * 0.11) + fi * 2.2) * 0.62;
            float orbitR = (1.45 + 0.35 * sin(t * 0.32 + fi * 1.4)) * (1.0 + 0.22 * u.bands0[i % 4]);
            vec3 dropPos = centerVoid + vec3(cos(ang) * orbitR, elev, sin(ang) * orbitR);
            dropPos.yz *= rot2(0.42 * sin(fi * 1.2 + t * 0.25));
            float dropR = 0.18 + 0.09 * u.bands1[i % 4] + 0.05 * beat;
            float dDrop = sdSphere(p - dropPos, dropR);
            dLiquid = smin(dLiquid, dDrop, 0.42 + 0.18 * bass);
        }

        // Multi-tier Relativistic Accretion Rings (Reflux Ergosphere)
        vec3 pRing1 = p - centerVoid;
        pRing1.xy *= rot2(0.52 + 0.07 * sin(t * 0.28));
        pRing1.yz *= rot2(1.22 + 0.11 * cos(t * 0.31 + midPhase * 0.18));
        float dRing1 = sdTorus(pRing1, vec2(radCore * 1.72 + 0.14 * mid, 0.038 + 0.020 * beat));

        vec3 pRing2 = p - centerVoid;
        pRing2.xy *= rot2(-0.45 - t * 0.18 - bassPhase * 0.12);
        pRing2.yz *= rot2(1.08 + 0.12 * sin(t * 0.24));
        float dRing2 = sdTorus(pRing2, vec2(radCore * 2.38 + 0.20 * subBass, 0.028 + 0.018 * lowMid));

        vec3 pHalo = p - vec3(0.0, -0.1, -0.3);
        pHalo.xz *= rot2(t * 0.07);
        pHalo.xy *= rot2(0.32 + 0.06 * sin(t * 0.19));
        float dHalo = sdTorus(pHalo, vec2(3.35 + 0.24 * bass, 0.035 + 0.022 * beat));

        float dRings = min(min(dRing1, dRing2), dHalo);

        // Axial Relativistic Void Jets / Energy Conduits
        vec3 pJet = p - centerVoid;
        float rJet = length(pJet.xz);
        float jetAngle = atan(pJet.z, pJet.x);
        float spiral = jetAngle - pJet.y * 3.2 + bassPhase * 1.6;
        float dJet = length(vec2(rJet - (0.24 + 0.16 * abs(pJet.y) * 0.35), 0.075 * sin(spiral * 2.0))) - (0.024 + 0.016 * mid);
        dJet = max(dJet, abs(pJet.y) - 2.85);

        // Kinetic Polyhedral Shards orbiting in equatorial plane
        float dShards = 1e5;
        for (int j = 0; j < 8; j++) {
            float fj = float(j);
            float sAng = -t * (0.45 + fj * 0.06) + fj * (TAU / 8.0) - midPhase * 0.28;
            float sRad = 1.95 + 0.42 * sin(fj * 2.0 + t * 0.5) + 0.22 * u.bands3[j % 4];
            vec3 sCenter = centerVoid + vec3(
                cos(sAng) * sRad,
                0.72 * sin(t * 0.52 + fj * 1.4),
                sin(sAng) * sRad
            );
            vec3 sp = p - sCenter;
            sp.xy *= rot2(sAng + highPhase * 0.32);
            sp.yz *= rot2(fj * 0.85 + t * 0.65);
            vec3 boxDim = vec3(0.19 + 0.12 * highMid, 0.016 + 0.008 * beat, 0.065 + 0.08 * u.bands2[j % 4]);
            dShards = min(dShards, sdBox(sp, boxDim));
        }

        vec2 res = vec2(dLiquid, 1.0);
        if (dRings < res.x)  res = vec2(dRings, 2.0);
        if (dJet < res.x)    res = vec2(dJet, 3.0);
        if (dShards < res.x) res = vec2(dShards, 4.0);
        return res;
    }

    // Twin Planetary System matching the cover art's two ringed glass worlds
    // World A (Upper-Right primary glass orb with multi-rings)
    vec3 centerA = vec3(
        1.15 + 0.35 * sin(t * 0.37 + bassPhase * 0.25),
        0.52 + 0.28 * cos(t * 0.29 + midPhase * 0.2),
        0.25 * sin(t * 0.31)
    );

    // World B (Lower-Left secondary glass orb with倾斜 rings & satellite moons)
    vec3 centerB = vec3(
        -1.25 + 0.38 * cos(t * 0.33 - bassPhase * 0.22),
        -0.45 + 0.30 * sin(t * 0.41 + midPhase * 0.18),
        -0.30 * cos(t * 0.27)
    );

    // Liquid surface ripple displacement driven by audio bands
    float rippleA = 0.045 * (0.35 + bass * 1.4) * sin(p.x * 7.0 + t * 2.5) * cos(p.y * 7.0 - t * 2.1) * sin(p.z * 7.0 + bassPhase);
    float rippleB = 0.040 * (0.35 + lowMid * 1.3) * cos(p.x * 8.5 - t * 2.2) * sin(p.y * 8.0 + t * 2.7);

    float radA = 0.68 + 0.16 * subBass + 0.08 * beat;
    float radB = 0.56 + 0.14 * bass + 0.06 * beat;

    float dOrbA = sdSphere(p - centerA, radA) + rippleA;
    float dOrbB = sdSphere(p - centerB, radB) + rippleB;

    // Satellite Liquid Droplets / Moons orbiting and fusing with the twin orbs (Liquid Metaballs)
    float dLiquid = smin(dOrbA, dOrbB, 0.55 + 0.25 * mid);

    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float ang = t * (0.55 + fi * 0.11) + fi * 1.047 + bassPhase * 0.35;
        float elev = sin(t * (0.4 + fi * 0.09) + fi * 2.1) * 0.65;
        float orbitR = (1.05 + 0.25 * sin(t * 0.3 + fi)) * (1.0 + 0.22 * u.bands0[i % 4]);
        vec3 anchor = (i < 3) ? centerA : centerB;
        vec3 dropPos = anchor + vec3(cos(ang) * orbitR, elev, sin(ang) * orbitR);
        float dropR = 0.16 + 0.09 * u.bands1[i % 4] + 0.04 * beat;
        float dDrop = sdSphere(p - dropPos, dropR);
        dLiquid = smin(dLiquid, dDrop, 0.38 + 0.15 * bass);
    }

    // Central Liquid Bridge / Plasma Core connecting CenterA and CenterB on strong beats
    float dBridge = sdCapsule(p, centerA, centerB, 0.09 + 0.11 * rms + 0.06 * beat);
    float bridgeWave = 0.04 * sin(length(p) * 9.0 - bassPhase * 2.0);
    dLiquid = smin(dLiquid, dBridge + bridgeWave, 0.48);

    // --- Material 2: Planetary Accretion Rings & Outer Cosmic Halo ---
    // Ring System A around World A
    vec3 pRingA = p - centerA;
    pRingA.xy *= rot2(-0.28 + 0.08 * sin(t * 0.25));
    pRingA.yz *= rot2(1.12 + 0.10 * cos(t * 0.32 + midPhase * 0.15));
    float dRingA1 = sdTorus(pRingA, vec2(radA * 1.62 + 0.12 * mid, 0.032 + 0.018 * highMid));
    float dRingA2 = sdTorus(pRingA, vec2(radA * 2.05 + 0.18 * treble, 0.020 + 0.015 * beat));
    // Sub-ring beneath Orb A (like the double-tiered pedestal ring on the cover)
    vec3 pSubRingA = pRingA - vec3(0.0, -0.52 - 0.08 * bass, 0.0);
    float dRingA3 = sdTorus(pSubRingA, vec2(radA * 0.85, 0.028 + 0.015 * lowMid));

    // Ring System B around World B
    vec3 pRingB = p - centerB;
    pRingB.xy *= rot2(0.42 + 0.09 * cos(t * 0.28));
    pRingB.yz *= rot2(1.05 - 0.12 * sin(t * 0.35 + bassPhase * 0.15));
    float dRingB1 = sdTorus(pRingB, vec2(radB * 1.68 + 0.14 * lowMid, 0.035 + 0.020 * bass));
    float dRingB2 = sdTorus(pRingB, vec2(radB * 2.15 + 0.16 * highMid, 0.022 + 0.014 * treble));

    // Giant Outer Sweeping Halo Arc (framing the lower-right & upper-right of the cover)
    vec3 pHalo = p - vec3(0.25, -0.35, -0.4);
    pHalo.xy *= rot2(0.35 + t * 0.05);
    pHalo.xz *= rot2(0.48 + 0.08 * sin(t * 0.18));
    float dHalo = sdTorus(pHalo, vec2(3.15 + 0.22 * subBass, 0.038 + 0.025 * beat));

    float dRings = min(min(dRingA1, dRingA2), min(dRingA3, min(dRingB1, min(dRingB2, dHalo))));

    // --- Material 3: Cascading Mycelial / Root-like Liquid Filaments ---
    // Inspired by the fibrous root-like light strands cascading from the right orb on the cover
    // and the organic connecting tendrils in procedural 3D art
    vec3 pTendril = p - (centerA + vec3(0.0, -0.3, 0.0));
    float rDist = length(pTendril.xz);
    float theta = atan(pTendril.z, pTendril.x);
    float numStrands = 14.0;
    float strandAngle = TAU / numStrands;
    float sector = floor((theta + PI) / strandAngle);
    float localTheta = mod(theta + PI, strandAngle) - 0.5 * strandAngle;

    // Curve strands outward smoothly as they cascade downward (continuous in theta to prevent sector seam slicing)
    float yFlow = pTendril.y;
    float targetRad = 0.38 + max(0.0, -yFlow) * (0.46 + 0.14 * sin(theta * 3.0 + t * 0.6));
    float waveTheta = 0.08 * sin(yFlow * 4.2 - bassPhase * 1.3 + sin(theta * 2.0)) / max(rDist, 0.35);
    vec2 strandDelta = vec2(
        rDist - targetRad - 0.07 * sin(yFlow * 5.5 + midPhase + theta * 4.0),
        (localTheta + waveTheta) * rDist
    );
    float dStrand = length(strandDelta) - (0.024 + 0.014 * mid);
    // Bound tendrils vertically so they cascade from the orb downwards
    dStrand = max(dStrand, abs(yFlow + 1.35) - 1.55);

    // Secondary interconnecting neural filaments across space
    vec3 pWeb = p;
    pWeb.xz *= rot2(t * 0.18 + bassPhase * 0.08);
    pWeb.yz *= rot2(t * 0.12);
    vec3 webTwist = pWeb + 0.32 * sin(pWeb.yzx * 1.8 + t * 0.7 + midPhase * 0.3);
    float dWeb = length( abs(fract(webTwist * 0.65) - 0.5) - vec3(0.0, 0.0, 0.42) ) - (0.014 + 0.014 * treble);
    // Keep web filaments near the orbital interaction zone
    dWeb = max(dWeb, length(p) - 3.6);

    float dTendrils = min(dStrand, dWeb) * 0.55;

    // --- Material 4: Kinetic Polyhedral Tech Shards & Fins ---
    // Sharp geometric plates & fins that orbit and articulate with mid/treble transients
    float dShards = 1e5;
    for (int j = 0; j < 8; j++) {
        float fj = float(j);
        float sAng = -t * (0.42 + fj * 0.05) + fj * (TAU / 8.0) - midPhase * 0.25;
        float sRad = 1.85 + 0.45 * sin(fj * 1.9 + t * 0.5) + 0.25 * u.bands3[j % 4];
        vec3 sCenter = ((j % 2 == 0) ? centerA : centerB) * 0.6 + vec3(
            cos(sAng) * sRad,
            0.75 * sin(t * 0.48 + fj * 1.3),
            sin(sAng) * sRad
        );
        vec3 sp = p - sCenter;
        sp.xy *= rot2(sAng + highPhase * 0.3);
        sp.yz *= rot2(fj * 0.8 + t * 0.6);
        vec3 boxDim = vec3(
            0.18 + 0.12 * highMid,
            0.016 + 0.008 * beat,
            0.06 + 0.08 * u.bands2[j % 4]
        );
        float dBoxShard = sdBox(sp, boxDim);
        dShards = min(dShards, dBoxShard);
    }

    // Determine closest surface and material ID
    vec2 res = vec2(dLiquid, 1.0);
    if (dRings < res.x)    res = vec2(dRings, 2.0);
    if (dTendrils < res.x) res = vec2(dTendrils, 3.0);
    if (dShards < res.x)   res = vec2(dShards, 4.0);

    return res;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.0025, -0.0025);
    return normalize(
        e.xyy * mapScene(p + e.xyy).x +
        e.yyx * mapScene(p + e.yyx).x +
        e.yxy * mapScene(p + e.yxy).x +
        e.xxx * mapScene(p + e.xxx).x
    );
}

vec2 mirrorUv(vec2 uv) {
    vec2 m = fract(uv * 0.5) * 2.0;
    return clamp(1.0 - abs(m - 1.0), 0.03, 0.97);
}

float calcAO(vec3 pos, vec3 nor) {
    float occ = 0.0;
    float sca = 1.0;
    for (int i = 0; i < 5; i++) {
        float h = 0.015 + 0.11 * float(i) / 4.0;
        float d = mapScene(pos + h * nor).x;
        occ += (h - d) * sca;
        sca *= 0.72;
    }
    return clamp(1.0 - 2.4 * occ, 0.0, 1.0);
}

// =============================================================================
// Background Cosmic Dreamworlds Nebula, Diagonal Light Beams & Paint Splatter Field
// =============================================================================
vec3 renderCosmicBackground(vec3 rd, vec2 screenUv) {
    float t = u.res.z;
    float bass = u.audio0.y;
    float mid = u.audio0.w;
    float treble = u.audio1.y;
    float beat = u.audio2.x;
    float bassPhase = u.audio2.y;
    float highPhase = u.audio2.w;

    if (u.preset.x > 0.5) {
        // --- PRESET 1: ORBITAL VOID REFLUX BACKGROUND ---
        // 1. Relativistic Gravitational Lensing of Cover_WMI_V2.png around void center
        vec2 centered = screenUv - 0.5;
        float r = length(centered);
        float theta = atan(centered.y, centered.x);

        float lensStrength = 0.075 * (1.0 + 0.35 * bass);
        float defl = lensStrength / (r + 0.08);
        vec2 lensedUv = centered * (1.0 - defl) + 0.5;
        lensedUv = (lensedUv - 0.5) * rot2(0.12 * sin(t * 0.25 - r * 3.5)) + 0.5;
        vec3 coverTex = texture(uCoverTex, mirrorUv(lensedUv)).rgb;

        float radVignette = smoothstep(0.92, 0.14, r);
        vec3 deepVoid = vec3(0.008, 0.004, 0.022);
        vec3 bg = mix(deepVoid, pow(coverTex, vec3(2.05)) * (0.42 + 0.30 * bass + 0.25 * beat), 0.50 + 0.50 * radVignette);

        // Photon ring accretion halo around singularity
        float photonRing = exp(-pow((r - 0.28) * 14.0, 2.0));
        vec3 ringFluxCol = mix(vec3(0.0, 0.94, 1.0), vec3(1.0, 0.0, 0.5), 0.5 + 0.5 * sin(theta * 3.0 + t));
        bg += ringFluxCol * photonRing * (0.35 + 0.45 * beat);

        // 2. Axial Relativistic Flux Shafts (Cyan / Radiant Magenta)
        vec2 fluxUv = (screenUv - 0.5) * rot2(0.42);
        float fluxMask = exp(-pow(fluxUv.x * (2.8 - 0.4 * bass), 2.0));
        float fluxStreaks = pow(0.5 + 0.5 * sin(fluxUv.x * 38.0 + sin(fluxUv.y * 7.0 + t * 0.9) * 2.2), 3.0);
        vec3 fluxCol = mix(
            vec3(0.00, 0.94, 1.00), // Electric Cyan
            vec3(0.61, 0.31, 0.87), // Reflux Violet
            0.5 + 0.5 * sin(fluxUv.y * 4.0 - t * 0.6)
        );
        fluxCol = mix(fluxCol, vec3(1.00, 0.00, 0.50), smoothstep(0.15, 0.45, abs(fluxUv.x)));
        bg += fluxCol * fluxMask * (0.16 + 0.24 * fluxStreaks) * (0.60 + 0.50 * mid + 0.35 * beat);

        // 3. Stardust & High-energy Accretion Particles
        for (int layer = 0; layer < 3; layer++) {
            float fl = float(layer);
            float scale = 14.0 + fl * 11.0;
            vec2 pUv = (screenUv - 0.5) * scale;
            pUv += vec2(sin(t * 0.11 * (fl + 1.0)), cos(t * 0.09 * (fl + 1.0))) * 1.8;
            vec2 cell = floor(pUv);
            vec2 f = fract(pUv) - 0.5;
            float h = hash21(cell + fl * 89.3);
            if (h > 0.54) {
                vec2 offset = (vec2(hash11(h * 23.3), hash11(h * 51.7)) - 0.5) * 0.55;
                float d = length(f - offset);
                float dotRad = (0.06 + 0.18 * hash11(h * 83.1)) * (0.85 + 0.45 * treble + 0.30 * beat);
                float splat = smoothstep(dotRad, dotRad * 0.12, d);
                vec3 splatCol = orbitalVoidPalette(h + fl * 0.25 + t * 0.03, mirrorUv(screenUv));
                bg += splatCol * splat * (0.28 + 0.30 * fl / 3.0);
            }
        }
        return bg;
    }

    // --- PRESET 0: COSMIC DREAMWORLDS BACKGROUND ---
    // 1. Deep Cosmic Void base with seamless 3D spherical/mirror projection of Cosmic Dreamworlds cover
    vec2 centered = (screenUv - 0.5) * 0.88;
    centered *= rot2(0.04 * sin(t * 0.14));
    vec2 flowUv = centered + 0.5 + 0.035 * vec2(
        sin(centered.y * 5.0 + t * 0.35 + bassPhase * 0.18),
        cos(centered.x * 5.0 - t * 0.30 + highPhase * 0.14)
    );
    vec3 coverTex = texture(uCoverTex, mirrorUv(flowUv)).rgb;

    // Deep space contrast: preserve stark obsidian cosmic depths so 3D liquid glass & rings pop
    float radVignette = smoothstep(0.95, 0.12, length(centered));
    vec3 deepVoid = vec3(0.012, 0.008, 0.035);
    vec3 bg = mix(deepVoid, pow(coverTex, vec3(2.15)) * (0.38 + 0.28 * bass + 0.22 * beat), 0.55 + 0.45 * radVignette);

    // 2. Diagonal Golden-Green-Magenta Aurora Light Shaft (iconic central beam from top-right to bottom-left)
    vec2 diagUv = (screenUv - 0.5) * rot2(-0.58); // ~ -33 deg diagonal
    float beamMask = exp(-pow(diagUv.x * (3.1 - 0.5 * bass), 2.0));
    float beamStreaks = pow(0.5 + 0.5 * sin(diagUv.x * 42.0 + sin(diagUv.y * 8.0 + t * 0.8) * 2.5), 3.0);
    vec3 beamColor = mix(
        vec3(0.08, 0.98, 0.32), // Cyber Emerald Green
        vec3(1.00, 0.92, 0.10), // Solar Yellow-Gold
        0.5 + 0.5 * sin(diagUv.y * 3.5 - t * 0.5)
    );
    beamColor = mix(beamColor, vec3(0.98, 0.08, 0.72), smoothstep(0.14, 0.42, abs(diagUv.x)));
    bg += beamColor * beamMask * (0.18 + 0.26 * beamStreaks) * (0.55 + 0.55 * mid + 0.35 * beat);

    // 3. Multi-layered 3D Cosmic Paint Splatter & Stardust Bokeh Field
    for (int layer = 0; layer < 3; layer++) {
        float fl = float(layer);
        float scale = 15.0 + fl * 12.0;
        vec2 pUv = (screenUv - 0.5) * scale;
        pUv += vec2(sin(t * 0.12 * (fl + 1.0)), cos(t * 0.10 * (fl + 1.0))) * 2.0;
        vec2 cell = floor(pUv);
        vec2 f = fract(pUv) - 0.5;
        float h = hash21(cell + fl * 73.1);
        if (h > 0.56) {
            vec2 offset = (vec2(hash11(h * 19.3), hash11(h * 47.7)) - 0.5) * 0.55;
            float d = length(f - offset);
            float dotRad = (0.07 + 0.19 * hash11(h * 91.1)) * (0.85 + 0.42 * treble + 0.28 * beat);
            float splat = smoothstep(dotRad, dotRad * 0.12, d);
            vec3 splatCol = cosmicPalette(h + fl * 0.23 + t * 0.03, mirrorUv(screenUv));
            bg += splatCol * splat * (0.26 + 0.32 * fl / 3.0);
        }
    }

    return bg;
}

void main() {
    vec2 fragCoord = vUv * u.res.xy;
    vec2 uv = (fragCoord - 0.5 * u.res.xy) / u.res.y;
    vec2 screenUv = vec2(vUv.x, vUv.y);

    float t = u.res.z;
    float subBass = u.audio0.x;
    float bass = u.audio0.y;
    float mid = u.audio0.w;
    float treble = u.audio1.y;
    float rms = u.audio1.w;
    float beat = u.audio2.x;
    float bassPhase = u.audio2.y;
    float midPhase = u.audio2.z;
    float highPhase = u.audio2.w;

    // --- Dynamic Orbital 3D Camera ---
    // Smoothly glides around the twin planetary liquid system and zooms on bass drops
    float camDist = 4.35 - 0.45 * bass - 0.22 * beat + 0.35 * sin(t * 0.19);
    float camYaw = t * 0.16 + 0.25 * sin(t * 0.11 + bassPhase * 0.08);
    float camPitch = 0.18 * sin(t * 0.14 + midPhase * 0.06);

    vec3 ro = vec3(
        sin(camYaw) * cos(camPitch) * camDist,
        sin(camPitch) * camDist + 0.15,
        cos(camYaw) * cos(camPitch) * camDist
    );
    vec3 ta = vec3(
        0.15 * sin(t * 0.23),
        0.10 * cos(t * 0.19),
        0.0
    );

    vec3 ww = normalize(ta - ro);
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = normalize(cross(uu, ww));
    // Subtle camera roll synced to low-mid groove
    float camRoll = 0.08 * sin(t * 0.21);
    vec2 rotUv = uv * rot2(camRoll);
    vec3 rd = normalize(rotUv.x * uu + rotUv.y * vv + (1.32 - 0.12 * beat) * ww);

    // Background Cosmic Dreamworlds canvas
    vec3 bgCol = renderCosmicBackground(rd, screenUv);
    vec3 col = bgCol;

    // --- Raymarching with Volumetric Glow Accumulation ---
    float tMax = 10.5;
    float dist = 0.0;
    float matId = 0.0;
    bool hit = false;

    vec3 glowAccum = vec3(0.0);

    for (int i = 0; i < 84; i++) {
        vec3 p = ro + rd * dist;
        vec2 h = mapScene(p);
        float d = h.x;

        // Accumulate tight volumetric neon bloom near rings, tendrils/jets, and liquid orbs (no wide haze washout)
        float glowFactor = exp(-d * 9.0) / (1.0 + d * d * 110.0);
        if (h.y == 2.0) {
            // Planetary / Accretion rings emit intense luminescence
            vec3 ringCol = getPresetPalette(length(p.xy) * 0.35 + t * 0.08, screenUv);
            glowAccum += ringCol * glowFactor * (0.016 + 0.022 * beat);
        } else if (h.y == 3.0) {
            // Tendrils or axial void jets emit pulsing luminescence
            vec3 tendrilCol = getPresetPalette(p.y * 0.4 - bassPhase * 0.15, screenUv);
            glowAccum += tendrilCol * glowFactor * (0.012 + 0.018 * treble);
        } else {
            vec3 orbGlow = getPresetPalette(0.65 + 0.2 * sin(t * 0.2), screenUv);
            glowAccum += orbGlow * glowFactor * 0.005;
        }

        if (d < 0.0022) {
            hit = true;
            matId = h.y;
            break;
        }
        if (dist > tMax) {
            break;
        }
        dist += d * 0.78;
    }

    if (hit) {
        vec3 p = ro + rd * dist;
        vec3 n = calcNormal(p);
        vec3 v = -rd;
        float ao = calcAO(p, n);

        // Key Lights: Solar Gold/White Beam from top-right + Electric Cobalt/Magenta Rim Light
        vec3 lightDir1 = normalize(vec3(0.65, 0.75, 0.45));
        vec3 lightDir2 = normalize(vec3(-0.75, -0.45, -0.50));

        float diff1 = max(dot(n, lightDir1), 0.0);
        float diff2 = max(dot(n, lightDir2), 0.0);
        float fresnel = pow(clamp(1.0 - max(dot(n, v), 0.0), 0.0, 1.0), 3.0);

        if (matId == 1.0) {
            // --- Material 1: Liquid Glass Planetary Orbs & Metaballs / Singularity Core ---
            // Chromatic dispersion refraction of the artwork & environment
            vec3 refrDirR = refract(rd, n, 1.0 / 1.44);
            vec3 refrDirG = refract(rd, n, 1.0 / 1.49);
            vec3 refrDirB = refract(rd, n, 1.0 / 1.54);

            vec2 refrUvR = mirrorUv(screenUv + refrDirR.xy * 0.24);
            vec2 refrUvG = mirrorUv(screenUv + refrDirG.xy * 0.24);
            vec2 refrUvB = mirrorUv(screenUv + refrDirB.xy * 0.24);

            vec3 refrCol;
            refrCol.r = texture(uCoverTex, refrUvR).r;
            refrCol.g = texture(uCoverTex, refrUvG).g;
            refrCol.b = texture(uCoverTex, refrUvB).b;

            // Deep translucent glass attenuation + internal iridescent swirling liquid caustics
            float coreDepth = pow(max(dot(n, v), 0.0), 1.6);
            float innerCaust = noise3(p * 3.8 + vec3(t * 0.45, -bassPhase * 0.3, midPhase * 0.25));
            vec3 innerSwatch = getPresetPalette(innerCaust + dot(n, vec3(0.4, 0.6, 0.2)), refrUvG);
            vec3 deepGlassCore = (u.preset.x > 0.5)
                ? mix(refrCol * 0.85, vec3(0.010, 0.005, 0.028), 0.52 * coreDepth)
                : mix(refrCol * 0.85, vec3(0.02, 0.05, 0.22), 0.45 * coreDepth);
            refrCol = mix(deepGlassCore, innerSwatch * (0.75 + 0.5 * diff1), 0.42 + 0.22 * bass);

            // Specular highlights & iridescent glass rim
            vec3 halfVec1 = normalize(lightDir1 + v);
            float spec1 = pow(max(dot(n, halfVec1), 0.0), 72.0);
            float spec2 = pow(max(dot(reflect(-lightDir2, n), v), 0.0), 36.0);

            vec3 rimColor = (u.preset.x > 0.5)
                ? mix(vec3(0.00, 0.94, 1.00), vec3(1.00, 0.00, 0.50), 0.5 + 0.5 * n.y)
                : mix(vec3(0.04, 0.92, 1.00), vec3(1.00, 0.12, 0.78), 0.5 + 0.5 * n.y);
            vec3 rimLight2 = (u.preset.x > 0.5) ? vec3(0.61, 0.31, 0.87) : vec3(0.12, 0.42, 1.00);

            col = refrCol * (0.65 + 0.45 * diff1) * (0.55 + 0.45 * ao)
                + rimColor * fresnel * (1.35 + 0.65 * rms)
                + vec3(1.0, 0.98, 0.92) * spec1 * (1.6 + 0.9 * beat)
                + rimLight2 * spec2 * 0.85;

        } else if (matId == 2.0) {
            // --- Material 2: Incandescent Planetary / Accretion Rings ---
            float ringWave = sin(length(p) * 18.0 - bassPhase * 2.5);
            vec3 ringBase;
            if (u.preset.x > 0.5) {
                ringBase = mix(
                    vec3(0.00, 0.94, 1.00), // Electric Reflux Cyan
                    vec3(1.00, 0.84, 0.12), // Accretion Flare Gold
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(1.00, 0.00, 0.50), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else {
                ringBase = mix(
                    vec3(0.98, 0.06, 0.14), // Crimson Red outer ring
                    vec3(1.00, 0.94, 0.18), // Incandescent Gold-White inner core
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(0.06, 0.98, 0.32), smoothstep(0.4, 0.9, sin(p.x * 6.0 + t)));
            }
            float spec = pow(max(dot(reflect(-lightDir1, n), v), 0.0), 48.0);
            col = ringBase * (0.55 + 0.65 * diff1) * ao * (1.25 + 0.80 * beat + 0.50 * mid)
                + ringBase * fresnel * 1.15
                + vec3(1.0) * spec * 0.95;

        } else if (matId == 3.0) {
            // --- Material 3: Cascading Mycelial Conduits / Axial Relativistic Jets ---
            float pulse = pow(0.5 + 0.5 * sin(p.y * 8.0 + bassPhase * 2.2), 4.0);
            vec3 strandCol = getPresetPalette(p.y * 0.25 + p.x * 0.15 + t * 0.05, mirrorUv(screenUv));
            float spec = pow(max(dot(reflect(-lightDir1, n), v), 0.0), 40.0);
            vec3 conduitFresnel = (u.preset.x > 0.5) ? vec3(0.00, 0.94, 1.00) : vec3(0.55, 0.88, 1.00);
            col = strandCol * (0.38 + 0.68 * diff1 + 0.25 * diff2) * ao
                + strandCol * pulse * (0.85 + 0.95 * bass)
                + conduitFresnel * fresnel * 0.95
                + vec3(1.0) * spec * 0.75;

        } else {
            // --- Material 4: Kinetic Polyhedral Shards ---
            // High-contrast obsidian & chrome plates reflecting neon splashes
            vec3 reflDir = reflect(rd, n);
            vec3 envRefl = renderCosmicBackground(reflDir, mirrorUv(screenUv + reflDir.xy * 0.15));
            float spec = pow(max(dot(reflect(-lightDir1, n), v), 0.0), 56.0);
            vec3 edgeGlow = getPresetPalette(p.z * 0.3 + highPhase * 0.1, mirrorUv(screenUv));
            col = mix(vec3(0.02, 0.03, 0.07), envRefl, 0.58 + 0.32 * fresnel) * ao
                + edgeGlow * fresnel * (1.2 + 0.9 * treble)
                + vec3(1.0) * spec * 1.35;
        }

        // Distance atmospheric blend into cosmic background
        float fog = smoothstep(5.2, tMax, dist);
        col = mix(col, bgCol, fog);
    }

    // Add volumetric luminescence
    col += glowAccum * (0.62 + 0.38 * rms + 0.32 * beat);

    // Subtle high-energy beat flash & chromatic edge bloom
    float vig = 1.0 - 0.26 * dot(uv, uv);
    col *= clamp(vig, 0.0, 1.0);

    // ACES-inspired filmic tone mapping while preserving vivid neon saturation
    col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
    col = pow(clamp(col, 0.0, 1.0), vec3(0.92));

    outColor = vec4(col, 1.0);
}
