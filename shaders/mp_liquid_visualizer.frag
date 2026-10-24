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
// Hexagonal Prism SDF (Defasten biomech plates & cyber armor)
float sdHexPrism(vec3 p, vec2 h) {
    const vec3 k = vec3(-0.8660254, 0.5, 0.57735);
    p = abs(p);
    p.xy -= 2.0 * min(dot(k.xy, p.xy), 0.0) * k.xy;
    vec2 d = vec2(
        length(p.xy - vec2(clamp(p.x, -k.z * h.x, k.z * h.x), h.x)) * sign(p.y - h.x),
        p.z - h.y
    );
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

// Cylinder SDF (Defasten structural spine & articulating robotic gimbals)
float sdCylinder(vec3 p, vec2 h) {
    vec2 d = abs(vec2(length(p.xz), p.y)) - h;
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

// Octahedron SDF (Stream of Frequency harmonic crystal nodes)
float sdOctahedron(vec3 p, float s) {
    p = abs(p);
    return (p.x + p.y + p.z - s) * 0.57735027;
}

// Dodecahedron SDF (Resonant Fluid Dynamics morphing tech core)
float sdDodecahedron(vec3 p, float r) {
    const vec3 n1 = normalize(vec3(0.0, 1.0, 1.61803398875));
    const vec3 n2 = normalize(vec3(0.0, 1.0, -1.61803398875));
    const vec3 n3 = normalize(vec3(1.0, 1.61803398875, 0.0));
    const vec3 n4 = normalize(vec3(-1.0, 1.61803398875, 0.0));
    const vec3 n5 = normalize(vec3(1.61803398875, 0.0, 1.0));
    const vec3 n6 = normalize(vec3(-1.61803398875, 0.0, 1.0));
    p = abs(p);
    float d = dot(p, n1);
    d = max(d, dot(p, n2));
    d = max(d, dot(p, n3));
    d = max(d, dot(p, n4));
    d = max(d, dot(p, n5));
    d = max(d, dot(p, n6));
    return d - r;
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

// Defasten Cyber Kinetic / Xinri D Signature Palette
// Inspired by Defasten - XINRI D - YAPORIGAMI & Start_Menu_Icon.png
vec3 defastenPalette(float t, vec2 uvHint) {
    vec3 colSakuraRibbon = vec3(1.00, 0.48, 0.68); // Luminous Kinetic Sakura Pink (#ff7aa8)
    vec3 colCyanCore     = vec3(0.00, 0.95, 1.00); // Supercharged Neon Cyan (#00f2ff)
    vec3 colChromeSteel  = vec3(0.72, 0.78, 0.85); // High-specular Titanium / Chrome Slate (#b8c7d9)
    vec3 colVoidBlack    = vec3(0.015, 0.018, 0.030);// Deep Obsidian Biomech Void (#040508)
    vec3 colLaserWhite   = vec3(0.98, 0.99, 1.00); // Pure White-Hot Laser Core (#fbfeff)
    vec3 colElectricViolet=vec3(0.68, 0.22, 0.95); // High-voltage Violet Accent (#ad37f2)

    float s = fract(t);
    vec3 procCol;
    if (s < 0.20) {
        procCol = mix(colVoidBlack, colChromeSteel, s * 5.0);
    } else if (s < 0.40) {
        procCol = mix(colChromeSteel, colCyanCore, (s - 0.20) * 5.0);
    } else if (s < 0.60) {
        procCol = mix(colCyanCore, colLaserWhite, (s - 0.40) * 5.0);
    } else if (s < 0.80) {
        procCol = mix(colLaserWhite, colSakuraRibbon, (s - 0.60) * 5.0);
    } else {
        procCol = mix(colSakuraRibbon, colElectricViolet, (s - 0.80) * 5.0);
    }

    vec2 texUv = fract(uvHint * 0.35 + vec2(0.5));
    vec3 coverSample = texture(uCoverTex, texUv).rgb;
    float luma = dot(coverSample, vec3(0.299, 0.587, 0.114));
    coverSample = clamp(mix(vec3(luma), coverSample, 1.48), 0.0, 1.0);

    return mix(procCol, coverSample, 0.42);
}

// Infinite Complexity Signature Palette
// Extracted directly from Cover_v4.png (MPlanetarian Bandcamp Covers)
vec3 infiniteComplexityPalette(float t, vec2 uvHint) {
    vec3 colObsidianVoid    = vec3(0.008, 0.004, 0.012); // Deep Obsidian Space Void (#020103)
    vec3 colDarkForest      = vec3(0.110, 0.180, 0.157); // Deep Emerald Forest Cyan-Teal (#1c2e28)
    vec3 colNeonMint        = vec3(0.165, 0.886, 0.467); // High-Voltage Neon Mint Green (#2ae277)
    vec3 colLuminousEmerald = vec3(0.584, 0.839, 0.667); // Radiant Mint / Emerald Glow (#95d6aa)
    vec3 colLavenderMist    = vec3(0.973, 0.910, 0.988); // Celestial Rose Quartz / Iridescent Lavender (#f8e8fc)
    vec3 colRoseQuartz      = vec3(0.894, 0.694, 0.757); // Soft Ethereal Rose Quartz (#e4b1c1)
    vec3 colMysticMagenta   = vec3(0.506, 0.224, 0.322); // Deep Mystic Magenta / Violet-Rose (#813952)
    vec3 colCosmicSage      = vec3(0.490, 0.569, 0.518); // Cosmic Sage Mist (#7d9184)
    vec3 colStarlightGold   = vec3(0.906, 0.898, 0.765); // Warm Starlight Gold Accent (#e7e5c3)

    float s = fract(t);
    vec3 procCol;
    if (s < 0.125) {
        procCol = mix(colObsidianVoid, colDarkForest, s * 8.0);
    } else if (s < 0.25) {
        procCol = mix(colDarkForest, colNeonMint, (s - 0.125) * 8.0);
    } else if (s < 0.375) {
        procCol = mix(colNeonMint, colLuminousEmerald, (s - 0.25) * 8.0);
    } else if (s < 0.50) {
        procCol = mix(colLuminousEmerald, colStarlightGold, (s - 0.375) * 8.0);
    } else if (s < 0.625) {
        procCol = mix(colStarlightGold, colLavenderMist, (s - 0.50) * 8.0);
    } else if (s < 0.75) {
        procCol = mix(colLavenderMist, colRoseQuartz, (s - 0.625) * 8.0);
    } else if (s < 0.875) {
        procCol = mix(colRoseQuartz, colMysticMagenta, (s - 0.75) * 8.0);
    } else {
        procCol = mix(colMysticMagenta, colCosmicSage, (s - 0.875) * 8.0);
    }

    vec2 texUv = fract(uvHint * 0.35 + vec2(0.5));
    vec3 coverSample = texture(uCoverTex, texUv).rgb;
    float luma = dot(coverSample, vec3(0.299, 0.587, 0.114));
    coverSample = clamp(mix(vec3(luma), coverSample, 1.52), 0.0, 1.0);

    return mix(procCol, coverSample, 0.44);
}

// Sensorium Interface & Defasten Earth Flipper Signature Palette
// Inspired by Sensorium_Interface.jpeg & Defasten - Yaporigami - Earth Flipper (2022)
vec3 sensoriumPalette(float t, vec2 uvHint) {
    vec3 colObsidianVoid     = vec3(0.020, 0.016, 0.032); // Deep Celestial Obsidian Void (#050408)
    vec3 colDeepSlate        = vec3(0.120, 0.140, 0.200); // Primordial Celestial Slate (#1f2433)
    vec3 colEarthFlipperJade = vec3(0.463, 0.576, 0.443); // Earth Flipper Moss/Jade Gold (#769371)
    vec3 colCyberCyan        = vec3(0.000, 0.961, 1.000); // Bioluminescent Cyber Cyan (#00f5ff)
    vec3 colRoseQuartz       = vec3(0.941, 0.659, 0.847); // Sensorium Rose Quartz (#f0a8d8)
    vec3 colCelestialPearl   = vec3(0.957, 0.914, 0.965); // Iridescent Celestial Pearl White (#f4e9f6)
    vec3 colRadiantOrchid    = vec3(0.722, 0.282, 0.769); // Radiant Sensorium Orchid Violet (#b848c4)
    vec3 colSolarBronze      = vec3(0.831, 0.761, 0.471); // Resonant Celestial Bronze (#d4c278)

    float s = fract(t);
    vec3 procCol;
    if (s < 0.142) {
        procCol = mix(colObsidianVoid, colDeepSlate, s * 7.042);
    } else if (s < 0.285) {
        procCol = mix(colDeepSlate, colEarthFlipperJade, (s - 0.142) * 7.0);
    } else if (s < 0.428) {
        procCol = mix(colEarthFlipperJade, colCyberCyan, (s - 0.285) * 7.0);
    } else if (s < 0.571) {
        procCol = mix(colCyberCyan, colCelestialPearl, (s - 0.428) * 7.0);
    } else if (s < 0.714) {
        procCol = mix(colCelestialPearl, colRoseQuartz, (s - 0.571) * 7.0);
    } else if (s < 0.857) {
        procCol = mix(colRoseQuartz, colRadiantOrchid, (s - 0.714) * 7.0);
    } else {
        procCol = mix(colRadiantOrchid, colSolarBronze, (s - 0.857) * 7.0);
    }

    vec2 texUv = fract(uvHint * 0.35 + vec2(0.5));
    vec3 coverSample = texture(uCoverTex, texUv).rgb;
    float luma = dot(coverSample, vec3(0.299, 0.587, 0.114));
    coverSample = clamp(mix(vec3(luma), coverSample, 1.48), 0.0, 1.0);

    return mix(procCol, coverSample, 0.45);
}

// Resonant Fluid Dynamics Signature Palette
// Inspired by Resonant Fluid Dynamics.png and Defasten - Earth Flipper
vec3 resonantFluidDynamicsPalette(float t, vec2 uvHint) {
    vec3 colAbyssalVoid     = vec3(0.031, 0.027, 0.067); // Deep Resonant Abyssal Indigo (#080711)
    vec3 colResonantIndigo  = vec3(0.086, 0.055, 0.620); // Deep Resonant Indigo / Ultramarine (#160e9e)
    vec3 colNeonOrchid      = vec3(0.894, 0.039, 0.655); // High-Voltage Neon Orchid Magenta (#e40aa7)
    vec3 colVioletPlum      = vec3(0.455, 0.043, 0.431); // Deep Violet Plum / Resonant Velvet (#740b6e)
    vec3 colRoseQuartz      = vec3(0.965, 0.592, 0.722); // Rose Quartz Luminous Pink (#f697b8)
    vec3 colElectricMint    = vec3(0.290, 0.867, 0.647); // Electric Mint Aqua / Bioluminescent Turquoise (#4adda5)
    vec3 colDeepViridian    = vec3(0.133, 0.537, 0.447); // Deep Viridian Wave (#228972)
    vec3 colStarlightPearl  = vec3(0.902, 0.945, 0.820); // Radiant Starlight Pearl / Pale Cream (#e6f1d1)

    float s = fract(t);
    vec3 procCol;
    if (s < 0.142) {
        procCol = mix(colAbyssalVoid, colResonantIndigo, s * 7.042);
    } else if (s < 0.285) {
        procCol = mix(colResonantIndigo, colNeonOrchid, (s - 0.142) * 7.0);
    } else if (s < 0.428) {
        procCol = mix(colNeonOrchid, colVioletPlum, (s - 0.285) * 7.0);
    } else if (s < 0.571) {
        procCol = mix(colVioletPlum, colRoseQuartz, (s - 0.428) * 7.0);
    } else if (s < 0.714) {
        procCol = mix(colRoseQuartz, colElectricMint, (s - 0.571) * 7.0);
    } else if (s < 0.857) {
        procCol = mix(colElectricMint, colDeepViridian, (s - 0.714) * 7.0);
    } else {
        procCol = mix(colDeepViridian, colStarlightPearl, (s - 0.857) * 7.0);
    }

    vec2 texUv = fract(uvHint * 0.35 + vec2(0.5));
    vec3 coverSample = texture(uCoverTex, texUv).rgb;
    float luma = dot(coverSample, vec3(0.299, 0.587, 0.114));
    coverSample = clamp(mix(vec3(luma), coverSample, 1.55), 0.0, 1.0);

    return mix(procCol, coverSample, 0.46);
}

vec3 getPresetPalette(float t, vec2 uvHint) {
    if (u.preset.x > 8.5) {
        return resonantFluidDynamicsPalette(t, uvHint);
    } else if (u.preset.x > 3.5) {
        return sensoriumPalette(t, uvHint);
    } else if (u.preset.x > 2.5) {
        return infiniteComplexityPalette(t, uvHint);
    } else if (u.preset.x > 1.5) {
        return defastenPalette(t, uvHint);
    } else if (u.preset.x > 0.5) {
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

    if (u.preset.x > 8.5) {
        // =========================================================================
        // PRESET 10: RESONANT FLUID DYNAMICS (DEFASTEN EARTH FLIPPER & DYNAMIC CORE)
        // Inspired by Defasten's "Yaporigami - Earth Flipper (2022)" & Resonant Fluid Dynamics:
        // "A primordial liquidstream of celestial origin spins itself back into existence 🌀🌌💦"
        // Elevated to supreme procedural complexity & dynamic fluidity:
        // 1. Central Transforming Liquid Orb / Polyhedral Tech Resonator (Material 1: Liquid Glass)
        //    Continuously morphs slowly over time between standing-wave fluid ripple sphere,
        //    faceted origami dodecahedron tech core, gyroscopic hyper-torus, and crystalline
        //    star-burst resonator seed. Sub-bass expands volume; audio bands modulate standing waves.
        // 2. Tri-Axis Interlocking Gyroscopic Fluid Toroids (Material 1 & 2)
        //    3 concentric, counter-precessing hydraulic liquid toroids undulating with standing waves.
        // 3. Braided Hex-Helical Primordial Liquidstreams (Material 3: Electric Mint & Neon Orchid)
        //    6 interwoven celestial fluid conduits winding along the spine, flexing with audio frequencies.
        // 4. Articulating Biomech Flipper Wings & Origami Sensorium Shards (Material 4: Obsidian Tech)
        //    8 articulated hexagonal/trapezoidal armor plates flapping in rhythmic sync with music transients.
        // 5. Relativistic Accretion Resonance Rings & Standing Waves (Material 2: Luminous Halos)
        //    Fine radial ripples glowing in electric mint, neon orchid, and radiant starlight cream.
        // 6. Floating Satellite Octahedron Crystal Nodes (Material 4: Harmonic Shards)
        // =========================================================================

        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;

        // Celestial spatial drift with non-linear harmonic pendulum motion
        vec3 centerFluid = vec3(
            0.15 * sin(dynTime * 0.055 + bassPhase * 0.07),
            0.11 * cos(dynTime * 0.045 + midPhase * 0.055),
            0.08 * sin(dynTime * 0.035)
        );
        vec3 pCore = p - centerFluid;

        // Monumental slow gyroscopic orientation
        pCore.yz *= rot2(0.38 + 0.05 * cos(dynTime * 0.035));
        pCore.xz *= rot2(dynTime * 0.048 + bassPhase * 0.028);
        pCore.xy *= rot2(0.12 * sin(dynTime * 0.04));

        // -------------------------------------------------------------------------
        // 1. Central Transforming Liquid Core (Material 1: Translucent Liquid Glass)
        // Morph cycle continuously transforms the central orb topology over time
        // -------------------------------------------------------------------------
        float morphT = fract(dynTime * 0.042);
        float rBase = 0.58 + 0.16 * subBass + 0.08 * beat;

        // Stage A: Viscous fluid ripple sphere with standing wave interference
        float rippleStanding = 0.048 * (0.35 + bass * 1.25) *
            sin(pCore.x * 6.5 + dynTime * 0.65 + bassPhase * 0.4) *
            cos(pCore.y * 6.5 - dynTime * 0.55 + midPhase * 0.3) *
            sin(pCore.z * 5.0 + dynTime * 0.45);
        float dFluidSphere = sdSphere(pCore, rBase) + rippleStanding;

        // Stage B: Faceted Origami Tech Dodecahedron with bevelled apertures
        vec3 pDodec = pCore;
        pDodec.xz *= rot2(dynTime * 0.12 + midPhase * 0.08);
        pDodec.yz *= rot2(dynTime * 0.09);
        float dDodec = sdDodecahedron(pDodec, rBase * 0.96) - 0.025;

        // Stage C: Gyroscopic non-Euclidean fluid hyper-torus
        vec3 pTorus = pCore;
        pTorus.xy *= rot2(dynTime * 0.15 + highPhase * 0.05);
        float dTorusCore = sdTorus(pTorus, vec2(rBase * 0.82, 0.22 + 0.06 * bass)) +
            0.025 * sin(pTorus.x * 8.0 + dynTime) * (1.0 + lowMid);

        // Stage D: Crystalline Octahedral Core Seed
        vec3 pOct = pCore;
        pOct.xz *= rot2(-dynTime * 0.10 + bassPhase * 0.06);
        float dOctaCore = sdOctahedron(pOct, rBase * 1.22);

        // Continuous cyclic smooth morphing between topologies
        float dMorphOrb;
        if (morphT < 0.25) {
            float f = morphT / 0.25;
            dMorphOrb = smin(dFluidSphere, dDodec, 0.22 * (1.0 - f) + 0.12 * f);
            dMorphOrb = mix(dFluidSphere, dDodec, smoothstep(0.0, 1.0, f));
        } else if (morphT < 0.50) {
            float f = (morphT - 0.25) / 0.25;
            dMorphOrb = smin(dDodec, dTorusCore, 0.18);
            dMorphOrb = mix(dDodec, dTorusCore, smoothstep(0.0, 1.0, f));
        } else if (morphT < 0.75) {
            float f = (morphT - 0.50) / 0.25;
            dMorphOrb = smin(dTorusCore, dOctaCore, 0.20);
            dMorphOrb = mix(dTorusCore, dOctaCore, smoothstep(0.0, 1.0, f));
        } else {
            float f = (morphT - 0.75) / 0.25;
            dMorphOrb = smin(dOctaCore, dFluidSphere, 0.22);
            dMorphOrb = mix(dOctaCore, dFluidSphere, smoothstep(0.0, 1.0, f));
        }

        // Inner glowing celestial pearl seed
        float dInnerSeed = sdSphere(pCore, 0.28 + 0.07 * beat);
        float dCentralCore = min(dMorphOrb, dInnerSeed);

        // -------------------------------------------------------------------------
        // 2. Tri-Axis Interlocking Gyroscopic Fluid Toroids (Material 1: Liquid Glass)
        // -------------------------------------------------------------------------
        vec3 pGyro1 = pCore;
        pGyro1.xz *= rot2(dynTime * 0.12 + bassPhase * 0.06);
        float rip1 = 0.032 * (0.35 + bass * 1.1) * sin(pGyro1.x * 5.5 + dynTime * 0.5) * cos(pGyro1.y * 5.5);
        float dGyro1 = sdTorus(pGyro1, vec2(1.22 + 0.16 * bass, 0.15 + 0.05 * subBass)) + rip1;

        vec3 pGyro2 = pCore;
        pGyro2.yz *= rot2(1.047 + dynTime * 0.09 - midPhase * 0.04);
        pGyro2.xy *= rot2(dynTime * 0.07);
        float rip2 = 0.028 * (0.35 + mid * 1.0) * sin(pGyro2.z * 5.5 - dynTime * 0.45);
        float dGyro2 = sdTorus(pGyro2, vec2(1.48 + 0.18 * lowMid, 0.13 + 0.04 * bass)) + rip2;

        vec3 pGyro3 = pCore;
        pGyro3.xy *= rot2(-1.047 + dynTime * 0.10 + highPhase * 0.05);
        pGyro3.xz *= rot2(-dynTime * 0.08);
        float rip3 = 0.025 * (0.30 + treble * 0.9) * cos(pGyro3.y * 6.0 + dynTime * 0.6);
        float dGyro3 = sdTorus(pGyro3, vec2(1.74 + 0.15 * mid, 0.11 + 0.03 * lowMid)) + rip3;

        float dLiquidGlass = smin(dCentralCore, dGyro1, 0.15);
        dLiquidGlass = smin(dLiquidGlass, dGyro2, 0.14);
        dLiquidGlass = smin(dLiquidGlass, dGyro3, 0.14);

        // -------------------------------------------------------------------------
        // 3. Relativistic Accretion Rings & Resonance Halos (Material 2: Luminous Halos)
        // -------------------------------------------------------------------------
        vec3 pHalo1 = pCore;
        pHalo1.yz *= rot2(0.24 + 0.04 * sin(dynTime * 0.05));
        float ringRipple1 = 0.015 * sin(length(pHalo1.xz) * 24.0 - dynTime * 1.8 + bassPhase * 1.4);
        float dHalo1 = sdTorus(pHalo1, vec2(2.10 + 0.22 * subBass + 0.08 * beat, 0.042 + 0.020 * beat)) + ringRipple1;

        vec3 pHalo2 = pCore;
        pHalo2.xz *= rot2(1.5707 + dynTime * 0.06);
        pHalo2.xy *= rot2(0.35);
        float ringRipple2 = 0.012 * cos(length(pHalo2.xz) * 20.0 - dynTime * 1.5);
        float dHalo2 = sdTorus(pHalo2, vec2(2.55 + 0.25 * bass, 0.035 + 0.018 * rms)) + ringRipple2;

        float dHalos = min(dHalo1, dHalo2);

        // -------------------------------------------------------------------------
        // 4. Braided Hex-Helical Primordial Liquidstreams (Material 3: Electric Mint & Neon Orchid)
        // 6 interwoven fluid streams twisting along the longitudinal spine
        // -------------------------------------------------------------------------
        float dLiquidStreams = 1e5;
        for (int i = 0; i < 6; i++) {
            float strandAngle = float(i) * (TAU / 6.0);
            float yRel = pCore.y;
            float twistRate = 1.35;
            float radHelix = 0.88 + 0.14 * sin(yRel * 2.2 + dynTime * 0.8 + float(i) * 1.047) + 0.12 * bass;
            float theta = yRel * twistRate + dynTime * 0.70 + float(i) * (TAU / 6.0) + bassPhase * 0.25;
            vec2 expectedXz = vec2(cos(theta), sin(theta)) * radHelix;
            float distToHelix = length(pCore.xz - expectedXz);
            float strandThick = 0.040 + 0.018 * sin(yRel * 3.5 + dynTime + float(i)) + 0.012 * mid;
            float dStrand = distToHelix - strandThick;
            dStrand = max(dStrand, abs(yRel) - 2.85); // Bound longitudinal length
            dLiquidStreams = min(dLiquidStreams, dStrand);
        }

        // -------------------------------------------------------------------------
        // 5. Articulating Biomech Flipper Wings & Origami Sensorium Shards (Material 4: Obsidian Tech)
        // 8 articulated hexagonal armor plates flapping in rhythmic sync with music
        // -------------------------------------------------------------------------
        float dFlippers = 1e5;
        float flapAngle = 0.32 * sin(dynTime * 0.85 + bassPhase * 0.75) * (1.0 + 0.95 * beat);
        for (int w = 0; w < 8; w++) {
            float wAngle = float(w) * (TAU / 8.0);
            vec3 pWing = pCore;
            pWing.xz *= rot2(wAngle + dynTime * 0.03);
            pWing.x -= (1.85 + 0.22 * bass + 0.12 * beat);
            pWing.yz *= rot2(flapAngle * ((w % 2 == 0) ? 1.0 : -1.0));
            pWing.xy *= rot2(0.18 * sin(dynTime * 0.6 + float(w)));
            float dPlate = sdHexPrism(pWing, vec2(0.36 + 0.05 * beat, 0.035));
            dFlippers = min(dFlippers, dPlate);
        }

        // -------------------------------------------------------------------------
        // 6. Floating Satellite Octahedron Crystal Nodes (Material 4: Harmonic Shards)
        // -------------------------------------------------------------------------
        float dSatellites = 1e5;
        for (int s = 0; s < 4; s++) {
            float sAngle = float(s) * (TAU / 4.0) + dynTime * 0.18;
            float sRad = 2.95 + 0.35 * sin(dynTime * 0.3 + float(s));
            vec3 pSat = pCore - vec3(cos(sAngle) * sRad, 0.6 * sin(sAngle * 2.0 + dynTime * 0.4), sin(sAngle) * sRad);
            pSat.xz *= rot2(dynTime * 0.8 + float(s));
            pSat.xy *= rot2(dynTime * 0.6);
            float dNode = sdOctahedron(pSat, 0.16 + 0.04 * treble);
            dSatellites = min(dSatellites, dNode);
        }
        float dTechArmor = min(dFlippers, dSatellites);

        // Consolidate scene distances and materials
        vec2 res = vec2(dLiquidGlass, 1.0);
        if (dHalos < res.x)          res = vec2(dHalos, 2.0);
        if (dLiquidStreams < res.x)  res = vec2(dLiquidStreams, 3.0);
        if (dTechArmor < res.x)      res = vec2(dTechArmor, 4.0);

        return res;
    } else if (u.preset.x > 3.5) {
        // --- PRESET 4: SENSORIUM INTERFACE (DEFASTEN EARTH FLIPPER CELESTIAL GYROSCOPE) ---
        // Inspired by Defasten's "Yaporigami - Earth Flipper (2022)" and Sensorium_Interface.jpeg:
        // "A primordial liquidstream of celestial origin spins itself back into existence 🌀🌌💦"
        // 1. Central Multi-Axis Gyroscopic Liquid Glass Core & Celestial Nucleus (Material 1)
        //    Slowly undulating with hydraulic harmonic wave ripples, spinning in non-Euclidean gyroscopic precession.
        // 2. Twin High-Energy Relativistic Accretion Halos & Resonance Rings (Material 2)
        //    Pulsing with bioluminescent cyber cyan, solar bronze, and beat transients.
        // 3. Braided Quad-Helical Primordial Liquidstreams & Sinuous Filaments (Material 3)
        //    Winding endlessly around the central spine, flexing with low-mid audio frequencies.
        // 4. Articulating Planetary Flipper Wings & Faceted Origami Sensorium Shards (Material 4)
        //    Hexagonal cyber-armor plates slowly flapping and articulating to music frequencies.

        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;

        // Slow, majestic celestial drift (slow-moving yet intricate)
        vec3 centerSensorium = vec3(
            0.12 * sin(dynTime * 0.06 + bassPhase * 0.08),
            0.09 * cos(dynTime * 0.05 + midPhase * 0.06),
            0.0
        );
        vec3 pCore = p - centerSensorium;

        // Monumental slow gyroscopic orientation
        pCore.yz *= rot2(0.32 + 0.04 * cos(dynTime * 0.04));
        pCore.xz *= rot2(dynTime * 0.05 + bassPhase * 0.03);
        pCore.xy *= rot2(0.10 * sin(dynTime * 0.045));

        // 1. Central Earth Flipper Gyroscopic Liquid Core & Primordial Nucleus (Material 1: Translucent Liquid Glass)
        // Celestial inner liquid glass sphere
        float dInnerOrb = sdSphere(pCore, 0.56 + 0.14 * subBass + 0.07 * beat);

        // Three interlocking gyroscopic liquid glass toroids with fluid ripple distortion
        float rippleA = 0.035 * (0.35 + bass * 1.15) * sin(pCore.x * 5.0 + dynTime * 0.40) * cos(pCore.y * 6.0 - dynTime * 0.35);
        float dGyroA = sdTorus(pCore, vec2(1.18 + 0.16 * bass, 0.16 + 0.05 * subBass)) + rippleA;

        vec3 pGyroB = pCore;
        pGyroB.xy *= rot2(1.0471975); // 60 degrees rotation
        pGyroB.yz *= rot2(0.5235987); // 30 degrees rotation
        float rippleB = 0.032 * (0.35 + mid * 1.10) * sin(pGyroB.y * 5.5 - dynTime * 0.38) * cos(pGyroB.z * 5.5 + dynTime * 0.30);
        float dGyroB = sdTorus(pGyroB, vec2(1.42 + 0.18 * mid, 0.13 + 0.04 * beat)) + rippleB;

        vec3 pGyroC = pCore;
        pGyroC.xz *= rot2(1.0471975);
        pGyroC.xy *= rot2(0.7853982);
        float rippleC = 0.030 * (0.35 + lowMid * 1.05) * cos(pGyroC.x * 6.0 + dynTime * 0.45);
        float dGyroC = sdTorus(pGyroC, vec2(1.68 + 0.20 * lowMid, 0.11 + 0.03 * bass)) + rippleC;

        float dCoreLiquid = smin(smin(dInnerOrb, dGyroA, 0.26), smin(dGyroB, dGyroC, 0.24), 0.20);

        // 2. High-Energy Relativistic Accretion Halos & Resonance Rings (Material 2: Luminous Cyber Cyan & Rose Quartz)
        vec3 pRing = pCore;
        pRing.xz *= rot2(dynTime * 0.07 + midPhase * 0.04);
        float dRingMain = sdTorus(pRing, vec2(2.15 + 0.24 * beat, 0.032 + 0.016 * beat));

        vec3 pRingPolar = pCore;
        pRingPolar.yz *= rot2(1.5707963);
        pRingPolar.xy *= rot2(dynTime * 0.05);
        float dRingPolar = sdTorus(pRingPolar, vec2(2.80 + 0.26 * subBass, 0.036 + 0.018 * mid));

        vec3 pHaloOuter = p - vec3(-0.15, 0.08, -0.25);
        pHaloOuter.xy *= rot2(0.38 + dynTime * 0.02);
        pHaloOuter.yz *= rot2(1.12 + 0.05 * sin(dynTime * 0.06));
        float dHaloOuter = sdTorus(pHaloOuter, vec2(3.45 + 0.28 * subBass, 0.032 + 0.018 * beat));
        float dResonanceRings = min(min(dRingMain, dRingPolar), dHaloOuter);

        // 3. Braided Quad-Helical Primordial Liquidstreams (Material 3: Earth Flipper Jade & Electric Cyan)
        float dLiquidStreams = 1e5;
        for (int k = 0; k < 4; k++) {
            float kf = float(k) * 1.5707963;
            float stAngle = dynTime * 0.08 + kf + bassPhase * 0.04;
            float radX = 1.80 + 0.30 * sin(stAngle * 2.0 + pCore.z * 1.4);
            float radY = 1.80 + 0.30 * cos(stAngle * 2.0 + pCore.z * 1.4);
            vec3 strandA = vec3(radX * cos(stAngle), radY * sin(stAngle), -1.8);
            vec3 strandB = vec3(radY * cos(stAngle + 0.8), radX * sin(stAngle + 0.8), 1.8);
            float dStrand = sdCapsule(pCore, strandA, strandB, 0.052 + 0.024 * mid);
            dStrand += 0.022 * sin(pCore.z * 7.0 - dynTime * 0.65 + bassPhase * 0.5) * (0.35 + bass);
            dLiquidStreams = min(dLiquidStreams, dStrand);
        }

        // 4. Articulating Planetary Flipper Wings & Faceted Origami Shards (Material 4: Obsidian Titanium Plates)
        float dFlippers = 1e5;
        for (int j = 0; j < 6; j++) {
            float angle = float(j) * 1.0471975 + dynTime * 0.025;
            float rad = 2.45 + 0.25 * sin(angle * 2.0 + dynTime * 0.04);
            // Majestic, slow flipper wing flap driven by audio frequencies
            float flap = 0.22 * sin(angle * 2.0 + dynTime * 0.10 + midPhase * 0.12) * (0.8 + 1.2 * mid);
            vec3 pF = pCore - vec3(rad * cos(angle), rad * sin(angle) + flap, 0.35 * sin(angle * 3.0));
            pF.xy *= rot2(angle + 1.5707963);
            pF.yz *= rot2(flap * 0.7);
            float dHex = sdHexPrism(pF, vec2(0.24 + 0.07 * treble, 0.042 + 0.015 * subBass));
            dFlippers = min(dFlippers, dHex);
        }

        vec2 res = vec2(dCoreLiquid, 1.0);
        if (dResonanceRings < res.x) res = vec2(dResonanceRings, 2.0);
        if (dLiquidStreams < res.x)  res = vec2(dLiquidStreams, 3.0);
        if (dFlippers < res.x)       res = vec2(dFlippers, 4.0);
        return res;
    }

    if (u.preset.x > 2.5) {
        // --- PRESET 3: INFINITE COMPLEXITY (DEFASTEN MIRRORED MADNESS) ---
        // Inspired by Defasten's "Mirrored Madness" (Neo Shibuya 2023) and Cover_v4.png:
        // An ecosystem of cyber organisms unfurling with hypercomplexity,
        // sinuous biomorphic contours, erratic fast snap movements and strange non-Euclidean folds,
        // tightly synchronized to audio frequencies and dynamic time frame modulation.

        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;

        // Rapid non-linear snap turns synced to bass transients
        float snapAngle = floor(bassPhase * 0.35) * 1.5707963 + smoothstep(0.0, 0.22, fract(bassPhase * 0.35)) * 1.5707963;
        // Micro-glitch saccade on transient peaks
        float twitch = (beat > 0.62 ? 0.085 : 0.0) * sin(highPhase * 7.5);

        // Cyber-organism floating spine center with dynamic drift
        vec3 centerOrg = vec3(
            0.18 * sin(dynTime * 0.32 + bassPhase * 0.22),
            0.12 * cos(dynTime * 0.26 + midPhase * 0.16),
            0.08 * sin(dynTime * 0.38 + highPhase * 0.12)
        );

        vec3 pFold = p - centerOrg;

        // Fast rotational motions and non-linear axial precession
        pFold.xz *= rot2(snapAngle + dynTime * 0.14 + twitch);
        pFold.xy *= rot2(0.34 * sin(dynTime * 0.25) + twitch * 0.55);
        pFold.yz *= rot2(0.28 * cos(dynTime * 0.20 + midPhase * 0.12));

        // Really strange movements: Defasten Mirrored Madness non-Euclidean space folding
        vec3 pOrg = pFold;
        pOrg.xy = abs(pOrg.xy) - vec2(0.40 + 0.14 * sin(dynTime * 0.42 + bassPhase * 0.25), 0.30 + 0.10 * cos(dynTime * 0.36));
        pOrg.xz *= rot2(0.58 + 0.16 * sin(dynTime * 0.28));
        pOrg.yz = abs(pOrg.yz) - vec2(0.24 + 0.08 * cos(dynTime * 0.46), 0.18);

        // 1. Sinuous Cyber Organism Core & Ribcage (Material 1: Translucent Liquid Glass)
        // Elongated segmented vertebrae spine
        float dSpine = sdCapsule(pOrg, vec3(0.0, -1.85, 0.0), vec3(0.0, 1.85, 0.0), 0.30 + 0.08 * subBass);
        // Sinuous biomorphic rib ripple that undulates along the spine
        float ribRipple = 0.038 * (0.35 + bass * 1.35) * sin(pOrg.y * 11.0 - bassPhase * 2.4) * cos(pOrg.x * 7.5 + dynTime);
        dSpine += ribRipple;
        // Spherical central power chamber at the core
        float dChamber = sdSphere(pFold - vec3(0.0, 0.0, 0.0), 0.64 + 0.14 * bass + 0.08 * beat);
        // Smooth fusion into a continuous organic cybernetic entity
        float dCyberCore = smin(dSpine, dChamber, 0.34 + 0.12 * mid);

        // 2. Incandescent Mirrored Kinetic Rings & Portal Arcs (Material 2: Glowing Neon Mint & White)
        vec3 pRing = pFold;
        pRing.xy *= rot2(dynTime * 0.44 + bassPhase * 0.32);
        float dRingA = sdTorus(pRing, vec2(1.18 + 0.18 * beat, 0.042 + 0.020 * beat));
        pRing.yz *= rot2(1.5707963);
        pRing.xz *= rot2(-dynTime * 0.52 - midPhase * 0.30);
        float dRingB = sdTorus(pRing, vec2(1.68 + 0.22 * mid, 0.036 + 0.016 * subBass));
        // Large outer framing halo ring tilted across the scene
        vec3 pHalo = pFold;
        pHalo.xy *= rot2(0.785398);
        pHalo.yz *= rot2(1.12 + 0.10 * sin(dynTime * 0.18));
        float dRingC = sdTorus(pHalo, vec2(2.95 + 0.28 * subBass, 0.038 + 0.022 * beat));
        float dRings = min(min(dRingA, dRingB), dRingC);

        // 3. Sinuous Biomorphic Contours & Cyber Tendrils (Material 3: Rose Quartz & Mystic Magenta)
        // Defasten signature: 4 interwoven parametric tendrils snaking along the cyber-organism
        float dTendrils = 1e5;
        for (int k = 0; k < 4; k++) {
            float fk = float(k);
            float ribOffset = fk * (TAU / 4.0);
            vec3 pT = pFold;
            float yRel = pT.y;
            float rTarget = 1.10 + 0.38 * sin(yRel * 1.05 + dynTime * 0.72 + fk) + 0.18 * u.bands1[k % 4];
            float angHelix = yRel * 1.55 - bassPhase * 1.45 + ribOffset;
            float curAng = atan(pT.z, pT.x);
            float deltaAng = mod(curAng - angHelix + PI, TAU) - PI;
            float distToHelix = length(vec2(length(pT.xz) - rTarget, deltaAng * rTarget * 0.48));
            float dStreamer = distToHelix - (0.025 + 0.016 * mid);
            dStreamer = max(dStreamer, abs(yRel) - 2.7);
            dTendrils = min(dTendrils, dStreamer);
        }

        // 4. Deconstructed Kinetic Origami Plates & Shards (Material 4: Titanium & Dark Forest Emerald)
        // Orbiting crystalline hexagonal plates that snap abruptly with transients
        float dOrigamiShards = 1e5;
        for (int m = 0; m < 8; m++) {
            float fm = float(m);
            float mAng = dynTime * (0.36 + fm * 0.06) + fm * (TAU / 8.0) + midPhase * 0.20;
            float mDist = 2.10 + 0.50 * sin(fm * 1.7 + dynTime * 0.42) + 0.24 * u.bands2[m % 4];
            vec3 hexPos = centerOrg + vec3(
                cos(mAng) * mDist,
                1.05 * sin(dynTime * 0.48 + fm * 1.25),
                sin(mAng) * mDist
            );
            vec3 ph = p - hexPos;
            ph.xy *= rot2(mAng * 1.25 + snapAngle * 0.45);
            ph.yz *= rot2(fm * 0.88 + dynTime * 0.58);
            float dHex = sdHexPrism(ph, vec2(0.26 + 0.13 * highMid, 0.020 + 0.009 * beat));
            dOrigamiShards = min(dOrigamiShards, dHex);
        }

        vec2 res = vec2(dCyberCore, 1.0);
        if (dRings < res.x)          res = vec2(dRings, 2.0);
        if (dTendrils < res.x)       res = vec2(dTendrils, 3.0);
        if (dOrigamiShards < res.x)  res = vec2(dOrigamiShards, 4.0);
        return res;
    }

    if (u.preset.x > 1.5) {
        // --- PRESET 2: DEFASTEN XINRI D (KINETIC BIOMECH CYBER-ORIGAMI) ---
        // Inspired by Defasten's XINRI D and Start_Menu_Icon.png:
        // 1. Central Biomechanical Aerodynamic Pod / Torpedo Engine (Frosted Pearlescent Liquid Glass)
        // 2. Twin High-Intensity Emissive Cyan Reactor Rings & Axial Drive Gimbals (Material 2)
        // 3. Swirling Helical Origami Sakura Ribbons & Tendrils wrapping the spine (Material 3)
        // 4. Floating Chrome Titanium Hexagon Armor Plates & Defasten Tech Shards (Material 4)

        vec3 centerSpine = vec3(
            0.15 * sin(t * 0.28 + bassPhase * 0.15),
            0.10 * cos(t * 0.22 + midPhase * 0.12),
            0.0
        );

        // Biomechanical orientation: tilted in 3D space like Defasten's composition
        vec3 pSpine = p - centerSpine;
        pSpine.xy *= rot2(-0.28 + 0.08 * sin(t * 0.18));
        pSpine.xz *= rot2(t * 0.14 + bassPhase * 0.08);
        pSpine.yz *= rot2(0.24 + 0.06 * cos(t * 0.20));

        // 1. Aerodynamic Biomechanical Core & Fuselage (Material 1: Frosted Pearlescent Glass)
        vec3 pPod = pSpine;
        float podRipple = 0.028 * (0.35 + bass * 1.2) * sin(pPod.z * 7.0 - bassPhase * 2.0) * cos(pPod.x * 5.0 + t);
        // Elongated central aerodynamic capsule
        float dCoreBody = sdCapsule(pPod, vec3(0.0, 0.0, -1.9), vec3(0.0, 0.0, 1.9), 0.38 + 0.06 * subBass) + podRipple;
        // Bulbous mid-fuselage engine housing
        float dEngineBulb = sdSphere(pPod - vec3(0.0, 0.05, 0.25 * sin(t * 0.4)), 0.58 + 0.10 * bass + 0.05 * beat);
        // Smin fusion to create organic aerodynamic contour
        float dPodSpine = smin(dCoreBody, dEngineBulb, 0.32 + 0.12 * mid);

        // 2. High-Intensity Emissive Cyan Reactor Rings & Drive Gimbals (Material 2: Glowing Neon)
        vec3 pRing = pSpine;
        pRing.yz *= rot2(1.5707963); // Perpendicular to spine axis z
        float dRingA = sdTorus(pRing - vec3(0.0, 0.85, 0.0), vec2(0.88 + 0.12 * beat, 0.042 + 0.02 * beat));
        float dRingB = sdTorus(pRing - vec3(0.0, -0.65, 0.0), vec2(0.96 + 0.14 * mid, 0.038 + 0.018 * subBass));
        float dRingC = sdTorus(pRing - vec3(0.0, -1.65, 0.0), vec2(0.65 + 0.16 * bass, 0.048 + 0.025 * beat));
        // Large outer framing halo ring
        vec3 pHalo = p - vec3(-0.2, 0.1, -0.2);
        pHalo.xy *= rot2(0.45 + t * 0.05);
        pHalo.yz *= rot2(1.15 + 0.08 * sin(t * 0.15));
        float dHaloDefasten = sdTorus(pHalo, vec2(3.10 + 0.22 * subBass, 0.035 + 0.02 * beat));
        float dRings = min(min(dRingA, dRingB), min(dRingC, dHaloDefasten));

        // 3. Swirling Helical Origami Sakura Ribbons (Material 3: Pink Tendrils / Streamers)
        // Defasten signature: 3 graceful helical streamers twisting along the main axis
        float dRibbons = 1e5;
        for (int k = 0; k < 3; k++) {
            float fk = float(k);
            float ribOffset = fk * (TAU / 3.0);
            vec3 pR = pSpine;
            float zRel = pR.z;
            // Helix radius expands gracefully towards the ends
            float rTarget = 1.35 + 0.35 * sin(zRel * 0.85 + t * 0.6 + fk) + 0.15 * u.bands1[k % 4];
            float angHelix = zRel * 1.35 - bassPhase * 1.4 + ribOffset;
            float currentAng = atan(pR.y, pR.x);
            float deltaAng = mod(currentAng - angHelix + PI, TAU) - PI;
            float distToHelix = length(vec2(length(pR.xy) - rTarget, deltaAng * rTarget * 0.45));
            float dStreamer = distToHelix - (0.026 + 0.016 * mid);
            dStreamer = max(dStreamer, abs(zRel) - 2.6); // Bound length along fuselage
            dRibbons = min(dRibbons, dStreamer);
        }

        // 4. Floating Chrome Titanium Hexagon Armor Plates & Defasten Origami Shards (Material 4)
        // Orbiting hexagonal tiles and tech shards that articulate with transients
        float dHexShards = 1e5;
        for (int m = 0; m < 8; m++) {
            float fm = float(m);
            float mAng = t * (0.35 + fm * 0.05) + fm * (TAU / 8.0) + midPhase * 0.18;
            float mDist = 1.95 + 0.45 * sin(fm * 1.8 + t * 0.4) + 0.22 * u.bands2[m % 4];
            vec3 hexCenter = centerSpine + vec3(
                cos(mAng) * mDist,
                0.80 * sin(t * 0.45 + fm * 1.3),
                sin(mAng) * mDist
            );
            vec3 ph = p - hexCenter;
            ph.xy *= rot2(mAng * 1.1 + highPhase * 0.22);
            ph.yz *= rot2(fm * 0.9 + t * 0.55);
            float dHex = sdHexPrism(ph, vec2(0.25 + 0.12 * highMid, 0.018 + 0.008 * beat));
            dHexShards = min(dHexShards, dHex);
        }

        vec2 res = vec2(dPodSpine, 1.0);
        if (dRings < res.x)     res = vec2(dRings, 2.0);
        if (dRibbons < res.x)   res = vec2(dRibbons, 3.0);
        if (dHexShards < res.x) res = vec2(dHexShards, 4.0);
        return res;
    }

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
    float rms = u.audio1.w;
    float beat = u.audio2.x;
    float bassPhase = u.audio2.y;
    float highPhase = u.audio2.w;

    if (u.preset.x > 8.5) {
        // --- PRESET 10: RESONANT FLUID DYNAMICS (DYNAMIC CONTINUOUS COLOR-CHANGING BACKGROUND) ---
        // 3D ray-projected celestial fluid manifold with infinite complexity design (dreamworlds),
        // continuously evolving background color palette, Defasten mirrored perspective grid,
        // chromatic dispersion 3D ray-sampling of Resonant Fluid Dynamics.png,
        // and volumetric quantum starlight dust drifting in 3D space.
        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;

        vec2 p3d = rd.xy / (abs(rd.z) + 0.08);

        // Fluid standing wave displacement in 3D space
        vec2 waveUv = p3d * 0.38;
        waveUv += vec2(
            sin(p3d.y * 3.2 + dynTime * 0.38 + bassPhase * 0.30),
            cos(p3d.x * 3.2 - dynTime * 0.32 + highPhase * 0.25)
        ) * (0.042 + 0.030 * bass);

        vec2 finalCoverUv = mix(mirrorUv(screenUv * 0.90 + 0.05), mirrorUv(waveUv + 0.5), 0.56);

        // Chromatic dispersion 3D ray-sampling of Resonant Fluid Dynamics.png
        float disp = 0.016 * (1.0 + 0.75 * beat);
        vec3 coverTex;
        coverTex.r = texture(uCoverTex, mirrorUv(finalCoverUv + rd.xy * disp)).r;
        coverTex.g = texture(uCoverTex, mirrorUv(finalCoverUv)).g;
        coverTex.b = texture(uCoverTex, mirrorUv(finalCoverUv - rd.xy * disp)).b;

        // Dynamic continuous color evolution of the background (changes colour continuously)
        float bgCycle = dynTime * 0.038;
        vec3 colA = mix(vec3(0.024, 0.018, 0.055), vec3(0.086, 0.055, 0.620), 0.5 + 0.5 * sin(bgCycle * 1.0)); // Deep Indigo shift
        vec3 colB = mix(vec3(0.894, 0.039, 0.655) * 0.32, vec3(0.290, 0.867, 0.647) * 0.28, 0.5 + 0.5 * sin(bgCycle * 1.4 + 1.2)); // Neon Magenta <-> Mint Aqua
        vec3 colC = mix(vec3(0.455, 0.043, 0.431) * 0.35, vec3(0.133, 0.537, 0.447) * 0.30, 0.5 + 0.5 * cos(bgCycle * 0.9 + 2.5)); // Violet Plum <-> Viridian

        vec3 colDeepSpace = mix(colA, colB, clamp(length(rd.xy) * 0.85, 0.0, 1.0));
        colDeepSpace = mix(colDeepSpace, colC, clamp(rd.y * 0.5 + 0.5, 0.0, 1.0));

        // Mirrored Defasten perspective grid planes
        float gridY = abs(rd.y);
        float gridLines = 0.0;
        if (gridY > 0.06) {
            vec2 gridCoord = rd.xz / (gridY + 0.001);
            gridCoord.y += dynTime * 0.25 + bassPhase * 0.15;
            vec2 gFract = abs(fract(gridCoord * 0.85) - 0.5);
            float gDist = min(gFract.x, gFract.y);
            gridLines = smoothstep(0.04, 0.0, gDist) * exp(-abs(gridCoord.y) * 0.18) * (0.35 + 0.45 * bass);
        }

        // Drifting quantum starlight dust
        vec3 starP = rd * 16.0;
        starP.xy += vec2(dynTime * 0.20, -dynTime * 0.15);
        float stars = pow(noise3(starP), 14.0) * (18.0 + 16.0 * treble);

        // Volumetric fluid fog & luminous aurora ripples
        float fluidAurora = 0.18 * sin(rd.x * 5.0 + rd.y * 4.0 + dynTime * 0.6 + bassPhase * 0.4);
        fluidAurora += 0.12 * cos(rd.x * 9.0 - rd.y * 7.0 - dynTime * 0.45);
        fluidAurora = clamp(fluidAurora, 0.0, 1.0) * (0.65 + 0.55 * mid);

        vec3 bgFinal = colDeepSpace + coverTex * (0.42 + 0.25 * rms)
            + vec3(0.290, 0.867, 0.647) * gridLines
            + vec3(0.965, 0.592, 0.722) * fluidAurora
            + vec3(0.902, 0.945, 0.820) * stars;

        return bgFinal;
    } else if (u.preset.x > 3.5) {
        // --- PRESET 4: SENSORIUM INTERFACE (DEFASTEN EARTH FLIPPER CELESTIAL BACKGROUND) ---
        // 3D ray-projected celestial void with primordial liquidstream parallax,
        // Sensorium_Interface.jpeg chromatic dispersion, auroral jade & mauve ripples,
        // and slow-drifting starlight fields reacting to audio frequencies.
        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;

        vec2 p3d = rd.xy / (abs(rd.z) + 0.08);

        // Slow-moving fluid wave displacement
        vec2 waveUv = p3d * 0.35;
        waveUv += vec2(
            sin(p3d.y * 2.8 + dynTime * 0.30 + bassPhase * 0.25),
            cos(p3d.x * 2.8 - dynTime * 0.25 + highPhase * 0.20)
        ) * (0.035 + 0.025 * bass);

        vec2 finalCoverUv = mix(mirrorUv(screenUv * 0.92 + 0.04), mirrorUv(waveUv + 0.5), 0.58);

        // Chromatic dispersion 3D ray-sampling of Sensorium_Interface.jpeg
        float disp = 0.014 * (1.0 + 0.65 * beat);
        vec3 coverTex;
        coverTex.r = texture(uCoverTex, mirrorUv(finalCoverUv + rd.xy * disp)).r;
        coverTex.g = texture(uCoverTex, mirrorUv(finalCoverUv)).g;
        coverTex.b = texture(uCoverTex, mirrorUv(finalCoverUv - rd.xy * disp)).b;

        // Celestial atmosphere: Deep obsidian slate with iridescent mauve and cyber cyan
        vec3 colDeepSpace = mix(
            vec3(0.016, 0.012, 0.028), // Deep Obsidian Void
            vec3(0.085, 0.105, 0.155), // Primordial Celestial Slate
            clamp(length(rd.xy) * 0.8, 0.0, 1.0)
        );

        // Undulating Earth Flipper auroral sheets
        float aurora = 0.5 + 0.5 * sin(atan(rd.y, rd.x) * 3.0 + length(rd.xy) * 5.0 - dynTime * 0.15);
        vec3 colAurora = mix(
            vec3(0.000, 0.961, 1.000), // Bioluminescent Cyber Cyan
            vec3(0.463, 0.576, 0.443), // Earth Flipper Jade
            aurora
        );

        // Starfield with audio shimmer
        float star = pow(hash21(floor(p3d * 42.0)), 26.0) * (1.0 + 2.5 * treble);
        vec3 colStars = vec3(0.957, 0.914, 0.965) * star;

        vec3 bg = mix(colDeepSpace, coverTex, 0.45) + colAurora * 0.18 * (0.7 + 0.6 * mid) + colStars;
        return bg;
    }

    if (u.preset.x > 2.5) {
        // --- PRESET 3: INFINITE COMPLEXITY 3D DYNAMIC BACKGROUND ---
        // Entirely 3D and dynamic background environment utilizing Cover_v4.png
        // with 3D ray-projected coordinates, dynamic undulating wave parallax,
        // chromatic dispersion, Defasten mirrored lattice grid, and floating quantum starlight.
        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;

        // 3D ray-planar projection for dynamic depth parallax
        vec2 p3d = rd.xy / (abs(rd.z) + 0.08);
        float r3d = length(p3d);

        // Dynamic 3D undulating wave displacement
        vec2 waveUv = p3d * 0.40;
        waveUv += vec2(
            sin(p3d.y * 3.6 + dynTime * 0.70 + bassPhase * 0.50),
            cos(p3d.x * 3.6 - dynTime * 0.60 + highPhase * 0.40)
        ) * (0.040 + 0.030 * bass);

        vec2 finalCoverUv = mix(mirrorUv(screenUv * 0.94 + 0.03), mirrorUv(waveUv + 0.5), 0.62);

        // Chromatic dispersion 3D ray-sampling of Cover_v4.png
        float disp = 0.016 * (1.0 + 0.75 * beat);
        vec3 coverTex;
        coverTex.r = texture(uCoverTex, mirrorUv(finalCoverUv + rd.xy * disp)).r;
        coverTex.g = texture(uCoverTex, mirrorUv(finalCoverUv)).g;
        coverTex.b = texture(uCoverTex, mirrorUv(finalCoverUv - rd.xy * disp)).b;

        // Atmospheric spatial gradient: Deep Obsidian Void (#020103) to Deep Dark Forest Emerald (#1c2e28)
        vec3 colVoid = vec3(0.008, 0.004, 0.012);
        vec3 colForest = vec3(0.040, 0.075, 0.065);
        vec3 bg = mix(colVoid, colForest, smoothstep(-0.85, 0.85, rd.y));

        // Dynamic 3D depth mask for cover texture
        float centerMask = smoothstep(2.4, 0.20, r3d);
        bg = mix(bg, pow(coverTex, vec3(1.72)) * (0.42 + 0.35 * bass + 0.25 * beat), 0.46 + 0.48 * centerMask);

        // 3D Defasten Mirrored Lattice grid receding into perspective depth
        vec2 latticeP = abs(p3d) * rot2(0.785398 + 0.06 * sin(dynTime * 0.22));
        float gridLines = sin(latticeP.x * 22.0 + dynTime * 0.8) * sin(latticeP.y * 22.0 - dynTime * 0.8);
        float gridMask = exp(-r3d * 0.80);
        vec3 latticeCol = mix(
            vec3(0.165, 0.886, 0.467), // Neon Mint Green (#2ae277)
            vec3(0.506, 0.224, 0.322), // Mystic Magenta (#813952)
            0.5 + 0.5 * sin(r3d * 5.5 - dynTime * 0.7)
        );
        bg += latticeCol * pow(abs(gridLines), 7.0) * gridMask * (0.32 + 0.42 * mid + 0.28 * beat);

        // 3D Starlight & Quantum Particulates drifting in 3D parallax
        for (int layer = 0; layer < 3; layer++) {
            float fl = float(layer);
            float scale = 14.0 + fl * 10.0;
            vec2 starUv = p3d * scale;
            starUv += vec2(sin(dynTime * 0.12 * (fl + 1.0)), cos(dynTime * 0.10 * (fl + 1.0))) * 2.2;
            vec2 cell = floor(starUv);
            vec2 f = fract(starUv) - 0.5;
            float h = hash21(cell + fl * 83.1);
            if (h > 0.48) {
                vec2 offset = (vec2(hash11(h * 31.7), hash11(h * 59.4)) - 0.5) * 0.6;
                float d = length(f - offset);
                float dotRad = (0.04 + 0.14 * hash11(h * 67.8)) * (0.85 + 0.55 * treble + 0.40 * beat);
                float splat = smoothstep(dotRad, dotRad * 0.10, d);
                vec3 starCol = infiniteComplexityPalette(h + fl * 0.25 + dynTime * 0.05, mirrorUv(screenUv));
                bg += starCol * splat * (0.35 + 0.35 * fl / 3.0);
            }
        }
        return bg;
    }

    if (u.preset.x > 1.5) {
        // --- PRESET 2: DEFASTEN XINRI D BACKGROUND ---
        // Clean high-tech cyber atmosphere inspired by Defasten's minimalist gradient sky
        // combined with refracted Start_Menu_Icon.png artwork, laser shafts, and floating debris
        vec2 centered = screenUv - 0.5;
        float r = length(centered);

        // Kinetic refraction distortion of Start_Menu_Icon.png
        vec2 warpUv = centered * (0.92 + 0.15 * sin(t * 0.35 - r * 4.0)) + 0.5;
        warpUv += 0.025 * vec2(
            sin(screenUv.y * 6.0 + bassPhase * 0.4),
            cos(screenUv.x * 6.0 - highPhase * 0.3)
        );
        vec3 coverTex = texture(uCoverTex, mirrorUv(warpUv)).rgb;

        // Clean high-contrast studio gradient (Slate titanium base fading into deep space)
        float gradY = screenUv.y;
        vec3 skyTop = vec3(0.045, 0.055, 0.080);   // Dark tech cyan slate
        vec3 skyBottom = vec3(0.012, 0.015, 0.024);// Deep obsidian void
        vec3 bg = mix(skyBottom, skyTop, gradY);

        // Overlay vibrant artwork texture softly so biomech geometry is razor-sharp
        float radMask = smoothstep(0.95, 0.18, r);
        bg = mix(bg, pow(coverTex, vec3(1.85)) * (0.36 + 0.25 * bass + 0.20 * beat), 0.42 + 0.48 * radMask);

        // Intense White-Hot & Cyan Vertical/Diagonal Laser Shafts
        vec2 laserUv = (screenUv - 0.5) * rot2(-0.35);
        float laserMask = exp(-pow(laserUv.x * (3.4 - 0.5 * bass), 2.0));
        float laserBeams = pow(0.5 + 0.5 * sin(laserUv.x * 46.0 + sin(laserUv.y * 9.0 + t * 1.2) * 2.8), 4.0);
        vec3 laserCol = mix(
            vec3(0.00, 0.95, 1.00), // Electric Cyan
            vec3(1.00, 0.48, 0.68), // Sakura Pink
            0.5 + 0.5 * sin(laserUv.y * 4.5 - t * 0.8)
        );
        laserCol = mix(laserCol, vec3(0.98, 0.99, 1.00), smoothstep(0.12, 0.35, abs(laserUv.x)));
        bg += laserCol * laserMask * (0.22 + 0.32 * laserBeams) * (0.65 + 0.55 * mid + 0.40 * beat);

        // Biomech Nano-dust & Floating Origami Confetti
        for (int layer = 0; layer < 3; layer++) {
            float fl = float(layer);
            float scale = 16.0 + fl * 12.0;
            vec2 pUv = (screenUv - 0.5) * scale;
            pUv += vec2(sin(t * 0.14 * (fl + 1.0)), cos(t * 0.12 * (fl + 1.0))) * 1.9;
            vec2 cell = floor(pUv);
            vec2 f = fract(pUv) - 0.5;
            float h = hash21(cell + fl * 97.4);
            if (h > 0.52) {
                vec2 offset = (vec2(hash11(h * 29.1), hash11(h * 61.3)) - 0.5) * 0.55;
                float d = length(f - offset);
                float dotRad = (0.05 + 0.16 * hash11(h * 77.2)) * (0.85 + 0.50 * treble + 0.35 * beat);
                float splat = smoothstep(dotRad, dotRad * 0.10, d);
                vec3 splatCol = defastenPalette(h + fl * 0.22 + t * 0.04, mirrorUv(screenUv));
                bg += splatCol * splat * (0.32 + 0.35 * fl / 3.0);
            }
        }
        return bg;
    }

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
    // Smoothly glides around the scene and zooms on bass drops
    float baseCamDist = (u.preset.x > 8.5) ? 5.35 : ((u.preset.x > 7.5) ? 5.30 : ((u.preset.x > 6.5) ? 5.10 : ((u.preset.x > 5.5) ? 5.15 : ((u.preset.x > 3.5) ? 5.20 : ((u.preset.x > 2.5) ? 5.25 : ((u.preset.x > 1.5) ? 5.10 : 4.35))))));
    float camDist = baseCamDist - 0.45 * bass - 0.22 * beat + 0.35 * sin(t * 0.19);
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
            vec3 deepGlassCore = (u.preset.x > 8.5)
                ? mix(refrCol * 0.94, vec3(0.015, 0.008, 0.035), 0.46 * coreDepth)
                : ((u.preset.x > 7.5)
                    ? mix(refrCol * 0.94, vec3(0.005, 0.008, 0.022), 0.46 * coreDepth)
                    : ((u.preset.x > 6.5)
                        ? mix(refrCol * 0.94, vec3(0.012, 0.005, 0.025), 0.46 * coreDepth)
                        : ((u.preset.x > 5.5)
                            ? mix(refrCol * 0.94, vec3(0.015, 0.008, 0.035), 0.46 * coreDepth)
                            : ((u.preset.x > 3.5)
                                ? mix(refrCol * 0.94, vec3(0.012, 0.010, 0.024), 0.46 * coreDepth)
                                : ((u.preset.x > 2.5)
                                    ? mix(refrCol * 0.94, vec3(0.008, 0.015, 0.012), 0.46 * coreDepth)
                                    : ((u.preset.x > 1.5)
                                        ? mix(refrCol * 0.92, vec3(0.015, 0.022, 0.038), 0.48 * coreDepth)
                                        : ((u.preset.x > 0.5)
                                            ? mix(refrCol * 0.85, vec3(0.010, 0.005, 0.028), 0.52 * coreDepth)
                                            : mix(refrCol * 0.85, vec3(0.02, 0.05, 0.22), 0.45 * coreDepth))))))));
            refrCol = mix(deepGlassCore, innerSwatch * (0.75 + 0.5 * diff1), 0.42 + 0.22 * bass);

            // Specular highlights & iridescent glass rim
            vec3 halfVec1 = normalize(lightDir1 + v);
            float spec1 = pow(max(dot(n, halfVec1), 0.0), 72.0);
            float spec2 = pow(max(dot(reflect(-lightDir2, n), v), 0.0), 36.0);

            vec3 rimColor = (u.preset.x > 8.5)
                ? mix(vec3(0.290, 0.867, 0.647), vec3(0.894, 0.039, 0.655), 0.5 + 0.5 * n.y)
                : ((u.preset.x > 7.5)
                    ? mix(vec3(0.220, 0.741, 0.973), vec3(0.984, 0.749, 0.141), 0.5 + 0.5 * n.y)
                    : ((u.preset.x > 6.5)
                        ? mix(vec3(0.000, 0.824, 1.000), vec3(1.000, 0.000, 0.502), 0.5 + 0.5 * n.y)
                        : ((u.preset.x > 5.5)
                            ? mix(vec3(0.000, 0.961, 0.831), vec3(0.969, 0.145, 0.522), 0.5 + 0.5 * n.y)
                            : ((u.preset.x > 3.5)
                                ? mix(vec3(0.000, 0.961, 1.000), vec3(0.941, 0.659, 0.847), 0.5 + 0.5 * n.y)
                                : ((u.preset.x > 2.5)
                                    ? mix(vec3(0.165, 0.886, 0.467), vec3(0.973, 0.910, 0.988), 0.5 + 0.5 * n.y)
                                    : ((u.preset.x > 1.5)
                                        ? mix(vec3(0.00, 0.95, 1.00), vec3(1.00, 0.48, 0.68), 0.5 + 0.5 * n.y)
                                        : ((u.preset.x > 0.5)
                                            ? mix(vec3(0.00, 0.94, 1.00), vec3(1.00, 0.00, 0.50), 0.5 + 0.5 * n.y)
                                            : mix(vec3(0.04, 0.92, 1.00), vec3(1.00, 0.12, 0.78), 0.5 + 0.5 * n.y))))))));
            vec3 rimLight2 = (u.preset.x > 8.5)
                ? vec3(0.455, 0.043, 0.431)
                : ((u.preset.x > 7.5)
                    ? vec3(0.984, 0.443, 0.522)
                    : ((u.preset.x > 6.5)
                        ? vec3(0.000, 1.000, 0.749)
                        : ((u.preset.x > 5.5)
                            ? vec3(0.420, 0.067, 1.000)
                            : ((u.preset.x > 3.5)
                                ? vec3(0.463, 0.576, 0.443)
                                : ((u.preset.x > 2.5)
                                    ? vec3(0.906, 0.898, 0.765)
                                    : ((u.preset.x > 1.5) ? vec3(0.98, 0.99, 1.00) : ((u.preset.x > 0.5) ? vec3(0.61, 0.31, 0.87) : vec3(0.12, 0.42, 1.00))))))));

            col = refrCol * (0.65 + 0.45 * diff1) * (0.55 + 0.45 * ao)
                + rimColor * fresnel * (1.35 + 0.65 * rms)
                + vec3(1.0, 0.98, 0.92) * spec1 * (1.6 + 0.9 * beat)
                + rimLight2 * spec2 * 0.85;

        } else if (matId == 2.0) {
            // --- Material 2: Incandescent Planetary / Accretion Rings ---
            float ringWave = sin(length(p) * 18.0 - bassPhase * 2.5);
            vec3 ringBase;
            if (u.preset.x > 8.5) {
                ringBase = mix(
                    vec3(0.290, 0.867, 0.647), // Electric Mint Aqua
                    vec3(0.894, 0.039, 0.655), // High-Voltage Neon Orchid
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(0.902, 0.945, 0.820), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else if (u.preset.x > 7.5) {
                ringBase = mix(
                    vec3(0.220, 0.741, 0.973), // Celestial Starlight Cyan
                    vec3(0.984, 0.749, 0.141), // Supernova Solar Gold
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(0.984, 0.443, 0.522), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else if (u.preset.x > 6.5) {
                ringBase = mix(
                    vec3(0.000, 0.824, 1.000), // Synchrotron Blue
                    vec3(0.000, 1.000, 0.749), // Cherenkov Aqua
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(1.000, 0.000, 0.502), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else if (u.preset.x > 5.5) {
                ringBase = mix(
                    vec3(0.000, 0.961, 0.831), // Electric Cotangent Cyan
                    vec3(0.969, 0.145, 0.522), // Non-Euclidean Prism Magenta
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(0.996, 0.894, 0.251), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else if (u.preset.x > 3.5) {
                ringBase = mix(
                    vec3(0.000, 0.961, 1.000), // Bioluminescent Cyber Cyan
                    vec3(0.941, 0.659, 0.847), // Sensorium Rose Quartz
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(0.722, 0.282, 0.769), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else if (u.preset.x > 2.5) {
                ringBase = mix(
                    vec3(0.165, 0.886, 0.467), // Neon Mint Green (#2ae277)
                    vec3(0.973, 0.910, 0.988), // Lavender Mist / White-hot core (#f8e8fc)
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(0.506, 0.224, 0.322), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else if (u.preset.x > 1.5) {
                ringBase = mix(
                    vec3(0.00, 0.95, 1.00), // Cyan Reactor Ring
                    vec3(0.98, 0.99, 1.00), // White-Hot Energy Beam
                    0.5 + 0.5 * ringWave
                );
                ringBase = mix(ringBase, vec3(1.00, 0.48, 0.68), smoothstep(0.35, 0.85, sin(p.x * 6.0 + t)));
            } else if (u.preset.x > 0.5) {
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
            vec3 conduitFresnel = (u.preset.x > 8.5)
                ? vec3(0.290, 0.867, 0.647) // Electric Mint Aqua
                : ((u.preset.x > 7.5)
                    ? vec3(0.220, 0.741, 0.973) // Starlight Cyan
                    : ((u.preset.x > 6.5)
                        ? vec3(0.000, 1.000, 0.749) // Cherenkov Aqua
                        : ((u.preset.x > 5.5)
                            ? vec3(0.000, 0.961, 0.831) // Cotangent Cyan
                            : ((u.preset.x > 3.5)
                                ? vec3(0.463, 0.576, 0.443) // Earth Flipper Celestial Jade
                                : ((u.preset.x > 2.5)
                                    ? vec3(0.894, 0.694, 0.757) // Rose Quartz
                                    : ((u.preset.x > 1.5) ? vec3(1.00, 0.48, 0.68) : ((u.preset.x > 0.5) ? vec3(0.00, 0.94, 1.00) : vec3(0.55, 0.88, 1.00))))))));
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
