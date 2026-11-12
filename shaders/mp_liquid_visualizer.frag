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

float valueNoise3(vec3 x) {
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
// Hexagonal Prism SDF (MPlanetarian biomech plates & cyber armor)
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

// Cylinder SDF (MPlanetarian structural spine & articulating robotic gimbals)
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

// MPlanetarian Cyber Kinetic / Xinri D Signature Palette
// Inspired by MPlanetarian - XINRI D - YAPORIGAMI & Start_Menu_Icon.png
vec3 mplanetarianPalette(float t, vec2 uvHint) {
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

// Sensorium Interface & MPlanetarian Earth Flipper Signature Palette
// Inspired by Sensorium_Interface.jpeg & MPlanetarian - Yaporigami - Earth Flipper (2022)
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
// Inspired by Resonant Fluid Dynamics.png and MPlanetarian - Earth Flipper
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

// =============================================================================
// Dreamworlds (Chromatic Storm) Signature Palette
// Inspired by MPlanetarian_Dreamworlds_Lockscreen.png and the late-sequence
// vessel forms of XI-N / MPlanetarian "BIFURCATION (2026)": layered chrome fins,
// glowing furnace interiors and dense bead swarms on a pale void.
// =============================================================================
vec3 chromaticStormPalette(float t, vec2 uvHint) {
    vec3 colPaleVoid   = vec3(0.902, 0.910, 0.936); // Bleached studio void
    vec3 colGraphite   = vec3(0.180, 0.185, 0.200); // Brushed hull plate
    vec3 colChrome     = vec3(0.760, 0.790, 0.850); // Polished fin chrome
    vec3 colFurnace    = vec3(1.000, 0.520, 0.110); // Molten furnace orange
    vec3 colEmberRed   = vec3(0.960, 0.180, 0.140); // Ember crimson
    vec3 colIceCyan    = vec3(0.180, 0.860, 1.000); // Cold plasma cyan
    vec3 colCobalt     = vec3(0.180, 0.320, 0.980); // Deep signal blue
    vec3 colMagenta    = vec3(0.960, 0.180, 0.780); // Chromatic storm magenta
    vec3 colAcidGreen  = vec3(0.420, 0.960, 0.320); // Acid verdigris

    float s = fract(t);
    vec3 procCol;
    if (s < 0.125) {
        procCol = mix(colPaleVoid, colChrome, s * 8.0);
    } else if (s < 0.250) {
        procCol = mix(colChrome, colGraphite, (s - 0.125) * 8.0);
    } else if (s < 0.375) {
        procCol = mix(colGraphite, colFurnace, (s - 0.250) * 8.0);
    } else if (s < 0.500) {
        procCol = mix(colFurnace, colEmberRed, (s - 0.375) * 8.0);
    } else if (s < 0.625) {
        procCol = mix(colEmberRed, colMagenta, (s - 0.500) * 8.0);
    } else if (s < 0.750) {
        procCol = mix(colMagenta, colCobalt, (s - 0.625) * 8.0);
    } else if (s < 0.875) {
        procCol = mix(colCobalt, colIceCyan, (s - 0.750) * 8.0);
    } else {
        procCol = mix(colIceCyan, colAcidGreen, (s - 0.875) * 8.0);
    }

    // Ground the palette in the artwork so the theme stays authentically rooted
    vec2 texUv = fract(uvHint * 0.35 + vec2(0.5));
    vec3 coverSample = texture(uCoverTex, texUv).rgb;
    float luma = dot(coverSample, vec3(0.299, 0.587, 0.114));
    coverSample = clamp(mix(vec3(luma), coverSample, 1.60), 0.0, 1.0);

    return mix(procCol, coverSample, 0.52);
}

// Ellipsoid SDF (teardrop hulls and furnace lobes)
float sdEllipsoidC(vec3 p, vec3 r) {
    float k0 = length(p / r);
    float k1 = length(p / (r * r));
    return k0 * (k0 - 1.0) / max(k1, 0.0001);
}

// A thin tapered fin blade grown along +X, broad in X-Y and thin in Z.
// This is the signature silhouette of the late BIFURCATION vessels.
float sdFinBlade(vec3 p, float len, float halfThick, float halfChord, float taper) {
    float u = clamp(p.x / max(len, 0.0001), 0.0, 1.0);
    float w = mix(1.0, taper, u);
    float dChord = abs(p.y) - halfChord * w;
    float dThick = abs(p.z) - halfThick * w;
    return max(max(dChord, dThick), max(-p.x, p.x - len));
}

// Smooth metaball union for fusing vessel lobes
float sminC(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / max(k, 0.0001), 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

// =============================================================================
// DREAMWORLDS (CHROMATIC STORM) — Shared scene kit
// The inspiration frames show elongated teardrop vehicles built from stacked
// chrome fins, split open to reveal a molten furnace core, with a dense swarm
// of black beads and fine wire trails trailing behind them across a pale void.
// Twelve sequences explore that vocabulary and morph continuously.
// =============================================================================

// Dense bead swarm trailing behind a vessel. Shared by every sequence; the
// hull, plume and furnace stay sequence-specific.
float csBeadTrail(vec3 p, float t, float spread, float lengthScale) {
    float d = 1e5;
    for (int i = 0; i < 16; i++) {
        float fi = float(i);
        vec3 h = hash33(vec3(fi * 1.7, fi * 3.1, fi * 0.9));
        float along = -0.6 - lengthScale * (0.35 + 1.55 * h.x) - 0.25 * sin(t * 0.35 + fi);
        float ang = h.y * TAU + t * (0.05 + 0.04 * h.z);
        float rad = spread * (0.20 + 0.95 * h.z);
        vec3 c = vec3(
            along,
            cos(ang) * rad,
            sin(ang) * rad
        );
        float sz = 0.008 + 0.020 * h.z + 0.006 * u.audio1.y;
        float bead = sdSphere(p - c, sz);
        // A third of the beads are punctured rings, as in the video
        if (h.x > 0.66) bead = max(bead, -sdSphere(p - c, sz * 0.55));
        d = min(d, bead);
    }
    return d;
}

// Fine graphite wire trails looping behind the vessel
float csWireTrail(vec3 p, float t) {
    float d = 1e5;
    for (int i = 0; i < 2; i++) {
        float fi = float(i);
        vec3 prev = vec3(0.0);
        for (int s = 0; s <= 26; s++) {
            float su = float(s) / 26.0;
            vec3 c = vec3(
                -0.5 - su * 2.35,
                0.46 * sin(su * 5.2 + fi * 2.0 + t * 0.22) * (0.35 + su),
                0.42 * cos(su * 3.4 + fi * 1.3 - t * 0.18) * (0.35 + su)
            );
            if (s > 0) d = min(d, sdCapsule(p, prev, c, 0.0038));
            prev = c;
        }
    }
    return d;
}

// -----------------------------------------------------------------------------
// SEQUENCE 1 — "FURNACE HULL"
// The hero vessel: a teardrop chrome shell split along its flank, with molten
// furnace light pouring out of the seam. This is the quiet anchor of the set.
// -----------------------------------------------------------------------------
vec2 csSeqFurnaceHull(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float bassPhase = u.audio2.y, midPhase = u.audio2.z;

    vec3 w = p - vec3(0.10 * sin(t * 0.05), 0.08 * cos(t * 0.06), 0.0);
    w.xz *= rot2(t * 0.06 + bassPhase * 0.03);
    w.yz *= rot2(0.14 * sin(t * 0.04));

    // Teardrop hull: a stretched ellipsoid with a tapered nose
    float dHull = sdEllipsoidC(w, vec3(1.42 + 0.10 * subBass, 0.46 + 0.05 * bass, 0.50 + 0.04 * mid));
    // Carve the furnace seam out of the flank so the core shows through
    vec3 seam = w;
    seam.xy *= rot2(0.16 + 0.05 * sin(t * 0.18));
    float dSeam = sdBox(seam - vec3(0.05, 0.0, 0.0), vec3(0.92 + 0.10 * bass, 0.30, 0.62));
    dHull = max(dHull, -dSeam);

    // Molten furnace core, pulsing with the beat (Material 2)
    float dFurnace = sdEllipsoidC(w, vec3(0.86 + 0.10 * subBass, 0.26 + 0.05 * beat, 0.30));
    dFurnace += 0.020 * (0.4 + bass) * sin(w.x * 8.0 + t * 1.2) * sin(w.z * 7.0 - t * 0.9);

    // Layered chrome fins stacked along the spine (Material 4)
    float dFins = 1e5;
    for (int i = 0; i < 7; i++) {
        float fi = float(i);
        float a = fi * 0.62 - 1.86;
        vec3 b = w;
        b.xy *= rot2(a);
        b.x -= 0.16 + 0.10 * hash11(fi * 3.1);
        float len = 1.05 + 0.55 * hash11(fi * 2.2) + 0.16 * treble;
        b.yz *= rot2(0.28 * sin(fi * 1.7 + t * 0.3));
        dFins = min(dFins, sdFinBlade(b, len, 0.012 + 0.006 * hash11(fi * 7.1), 0.13 + 0.09 * hash11(fi * 5.3), 0.16));
    }

    vec2 res = vec2(dHull, 1.0);
    if (dFins < res.x)    res = vec2(dFins, 4.0);
    if (dFurnace < res.x) res = vec2(dFurnace, 2.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 2 — "FIN CASCADE"
// The vessel disassembles into a cascading procession of chrome fins, like a
// wing opening feather by feather along the direction of travel.
// -----------------------------------------------------------------------------
vec2 csSeqFinCascade(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float bassPhase = u.audio2.y, highPhase = u.audio2.w;

    vec3 w = p - vec3(0.06 * sin(t * 0.06), 0.05 * cos(t * 0.05), 0.0);
    w.xz *= rot2(t * 0.075);

    float dFins = 1e5;
    for (int i = 0; i < 14; i++) {
        float fi = float(i);
        // Fins march back along the hull and fan wider as they recede
        float along = 0.85 - fi * 0.155;
        float open = 0.22 + 0.32 * sin(t * 0.55 + fi * 0.42) + 0.16 * beat;
        vec3 b = w;
        b.x -= along;
        b.xy *= rot2(open * (0.5 + 0.5 * hash11(fi * 2.1)));
        b.yz *= rot2(0.55 * sin(fi * 1.3 + t * 0.28) + 0.2 * mid);
        float len = 0.85 + 0.55 * hash11(fi * 4.7) + 0.18 * treble;
        dFins = min(dFins, sdFinBlade(b, len, 0.012 + 0.006 * hash11(fi * 3.3), 0.17 + 0.13 * hash11(fi * 6.1), 0.14));
    }

    // Slim spine running through the fin array
    float dSpine = sdCapsule(w, vec3(1.10, 0.0, 0.0), vec3(-1.30, 0.0, 0.0), 0.115 + 0.030 * subBass);
    dSpine += 0.014 * (0.4 + bass) * sin(w.x * 9.0 - t * 1.1 + highPhase * 0.3);

    vec2 res = vec2(dSpine, 1.0);
    if (dFins < res.x) res = vec2(dFins, 4.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 3 — "SPLIT KEEL"
// The vessel's belly opens into two long parallel keels, baring a bright
// plasma channel between them, echoing the widest-open frames.
// -----------------------------------------------------------------------------
vec2 csSeqSplitKeel(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float bassPhase = u.audio2.y;

    vec3 w = p - vec3(0.07 * sin(t * 0.07), 0.06 * cos(t * 0.05), 0.0);
    w.xy *= rot2(0.12 * sin(t * 0.045));

    float gap = 0.26 + 0.18 * bass + 0.10 * beat + 0.05 * sin(t * 0.7);

    // Two long keels, each built from a flat tapered blade plus a rib so the
    // structure reads as machined metal rather than an elongated pod.
    float dKeel = 1e5;
    for (int i = 0; i < 2; i++) {
        float sgn = float(i) * 2.0 - 1.0;
        vec3 b = w - vec3(0.0, sgn * gap, 0.0);
        b.xz *= rot2(sgn * 0.10 * sin(t * 0.3));
        // Flat blade along X (broad in XY, thin in Z)
        vec3 bb = b;
        bb.x += 1.62;
        float dBlade = sdFinBlade(bb, 3.24 + 0.16 * subBass, 0.030, 0.115 + 0.030 * bass, 0.30);
        // Structural rib running the length of the keel
        float dRib = sdCapsule(b, vec3(1.45, 0.0, 0.0), vec3(-1.45, 0.0, 0.0), 0.040);
        dKeel = min(dKeel, min(dBlade, dRib));
    }

    // Bright plasma channel suspended between the keels (Material 2)
    float dPlasma = sdCapsule(w, vec3(1.42, 0.0, 0.0), vec3(-1.42, 0.0, 0.0), 0.062 + 0.026 * beat);
    dPlasma += 0.014 * (0.5 + bass) * sin(w.x * 12.0 - t * 1.6 + bassPhase * 0.4);

    // Fins splaying off each keel
    float dFins = 1e5;
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float sgn = mod(fi, 2.0) * 2.0 - 1.0;
        vec3 b = w - vec3(0.0, sgn * (gap + 0.12), 0.0);
        b.xy *= rot2(sgn * (0.55 + 0.25 * sin(t * 0.4 + fi)));
        b.x -= 0.55 - fi * 0.14;
        dFins = min(dFins, sdFinBlade(b, 0.70 + 0.30 * hash11(fi * 3.9), 0.009, 0.09 + 0.05 * hash11(fi * 2.3), 0.14));
    }

    vec2 res = vec2(dKeel, 4.0);
    if (dFins < res.x)   res = vec2(dFins, 4.0);
    if (dPlasma < res.x) res = vec2(dPlasma, 2.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 4 — "BEAD SURGE"
// The bead swarm takes over: hundreds of perforated spheres rushing past in a
// dense river, with the vessel reduced to a silhouette deep inside it.
// -----------------------------------------------------------------------------
vec2 csSeqBeadSurge(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;

    vec3 w = p - vec3(0.10 * sin(t * 0.08), 0.08 * cos(t * 0.06), 0.0);
    w.yz *= rot2(t * 0.10);

    // Dense river of beads streaming down the X axis
    float dBeads = 1e5;
    for (int i = 0; i < 40; i++) {
        float fi = float(i);
        vec3 h = hash33(vec3(fi * 2.3, fi * 5.1, fi * 1.3));
        // Beads flow continuously: the mod wraps each one back to the front
        float flow = mod(h.x * 6.0 + t * (0.55 + 0.35 * h.y), 6.0) - 3.0;
        float ang = h.z * TAU + t * 0.14;
        float rad = 0.10 + 1.05 * h.y * h.z;
        vec3 c = vec3(flow, cos(ang) * rad, sin(ang) * rad);
        float sz = 0.012 + 0.034 * h.z + 0.014 * treble;
        float bead = sdSphere(w - c, sz);
        if (h.x > 0.55) bead = max(bead, -sdSphere(w - c, sz * 0.5));
        dBeads = min(dBeads, bead);
    }

    // The vessel silhouette buried in the surge (dark hull material)
    float dHull = sdEllipsoidC(w, vec3(1.15 + 0.06 * bass, 0.30 + 0.04 * mid, 0.34));
    dHull = max(dHull, -sdBox(w - vec3(0.0, 0.0, 0.0), vec3(0.55, 0.16, 0.5)));

    vec2 res = vec2(dHull, 1.0);
    if (dBeads < res.x) res = vec2(dBeads, 5.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 5 — "EMBER WAKE"
// A slow, ember-lit vessel coasting with a long fiery wake streaking behind it.
// -----------------------------------------------------------------------------
vec2 csSeqEmberWake(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y;
    float treble = u.audio1.y, beat = u.audio2.x;
    float bassPhase = u.audio2.y;

    vec3 w = (p - vec3(0.05 * sin(t * 0.04), 0.04 * cos(t * 0.05), 0.0)) * 0.62;
    w.xz *= rot2(t * 0.05);

    // Compact hull at the head of the wake
    float dHull = sdEllipsoidC(w, vec3(0.92 + 0.07 * subBass, 0.34 + 0.04 * bass, 0.38));
    float dSeam = sdBox(w - vec3(0.10, 0.0, 0.0), vec3(0.55, 0.20, 0.50));
    dHull = max(dHull, -dSeam);

    // Molten core inside the seam
    float dCore = sdEllipsoidC(w, vec3(0.52, 0.16 + 0.04 * beat, 0.22));
    dCore += 0.016 * (0.4 + bass) * sin(w.x * 10.0 + t * 1.4);

    // Long ember wake trailing backwards, breaking into ember lobes
    float dWake = 1e5;
    for (int i = 0; i < 14; i++) {
        float fi = float(i);
        float along = -0.80 - fi * 0.20;
        float sway = 0.13 * sin(t * 0.55 + fi * 0.8 + bassPhase * 0.2);
        vec3 c = vec3(along, sway * (0.3 + 0.07 * fi), 0.09 * cos(fi * 1.7 + t * 0.4));
        float sz = (0.062 - fi * 0.0028) * (0.85 + 0.5 * hash11(fi * 3.7)) + 0.014 * treble;
        dWake = min(dWake, sdEllipsoidC(w - c, vec3(sz * 2.4, sz, sz)));
    }

    // Fins along the hull
    float dFins = 1e5;
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        vec3 b = w;
        b.xy *= rot2(fi * 0.8 - 1.6);
        b.x -= 0.10;
        dFins = min(dFins, sdFinBlade(b, 0.80 + 0.30 * hash11(fi * 2.9), 0.010, 0.11, 0.16));
    }

    vec2 res = vec2(dHull, 1.0);
    if (dFins < res.x)  res = vec2(dFins, 4.0);
    if (dWake < res.x)  res = vec2(dWake, 2.0);
    if (dCore < res.x)  res = vec2(dCore, 3.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 6 — "PLASMA COCOON"
// The vessel wraps itself in a luminous plasma cocoon that tightens and
// loosens with the music, the hull barely visible inside.
// -----------------------------------------------------------------------------
vec2 csSeqPlasmaCocoon(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float midPhase = u.audio2.z;

    vec3 w = p - vec3(0.08 * sin(t * 0.06), 0.06 * cos(t * 0.07), 0.0);
    w.xz *= rot2(t * 0.055 + midPhase * 0.02);

    // Inner hull (dark, material 1)
    float dHull = sdEllipsoidC(w, vec3(1.10, 0.30, 0.34));

    // Plasma cocoon: luminous orbital rings and tendrils wrapping the hull.
    // A solid emissive shell would simply hide the vessel in an opaque
    // raymarcher, so the cocoon is built from discrete glowing bands instead.
    float breathe = 1.0 + 0.12 * sin(t * 0.75) + 0.07 * beat;
    float dCocoon = 1e5;
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        // Torus rings encircling the hull's long axis. sdTorus measures
        // radius in p.xz and height in p.y, so swapping the axes puts the
        // ring around X instead of Y.
        vec3 b = w - vec3((fi - 2.0) * 0.44, 0.0, 0.0);
        b.yz *= rot2(0.40 * sin(t * 0.35 + fi * 0.9) + 0.16 * bass);
        vec3 q = vec3(b.z, b.x, b.y);
        float majorR = (0.46 + 0.03 * fi) * breathe;
        dCocoon = min(dCocoon, sdTorus(q, vec2(majorR, 0.014 + 0.006 * bass)));
    }
    // Longitudinal plasma tendrils lacing the bands together
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float a = fi * 1.0472 + t * 0.20;
        vec3 top = vec3(1.02, cos(a) * 0.46 * breathe, sin(a) * 0.50 * breathe);
        vec3 bot = vec3(-1.02, cos(a) * 0.46 * breathe, sin(a) * 0.50 * breathe);
        dCocoon = min(dCocoon, sdCapsule(w, top, bot, 0.012 + 0.006 * bass));
    }

    // Fine plasma filaments lacing the cocoon
    float dFil = 1e5;
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float a = fi * 1.0472 + t * 0.16;
        vec3 top = vec3(1.15, cos(a) * 0.42, sin(a) * 0.44);
        vec3 bot = vec3(-1.15, cos(a + 2.0) * 0.42, sin(a + 2.0) * 0.44);
        dFil = min(dFil, sdCapsule(w, top, bot, 0.010 + 0.006 * treble));
    }

    vec2 res = vec2(dHull, 1.0);
    if (dFil < res.x)    res = vec2(dFil, 4.0);
    if (dCocoon < res.x) res = vec2(dCocoon, 2.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 7 — "SPINE RING"
// The hull reduces to a structural spine ringed by counter-rotating gyros of
// chrome plate, the frame skeleton of the vessel.
// -----------------------------------------------------------------------------
vec2 csSeqSpineRing(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float highPhase = u.audio2.w;

    vec3 w = p - vec3(0.05 * sin(t * 0.05), 0.05 * cos(t * 0.04), 0.0);
    w.xy *= rot2(0.16 * sin(t * 0.05));

    // Central spine
    float dSpine = sdCapsule(w, vec3(1.45, 0.0, 0.0), vec3(-1.45, 0.0, 0.0), 0.085 + 0.020 * subBass);

    // Three counter-rotating plate gyros around the spine (Material 4)
    float dGyros = 1e5;
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float a = fi * 1.0472;
        vec3 b = w;
        b.yz *= rot2(a + t * (0.22 + 0.08 * fi) + highPhase * 0.05);
        float rad = 0.62 + fi * 0.16 + 0.06 * bass;
        b.yz -= vec2(rad, 0.0);
        b.xz *= rot2(t * (0.16 - 0.04 * fi));
        float dPlate = sdFinBlade(b, 0.95 + 0.20 * hash11(fi * 3.1), 0.011, 0.15 + 0.05 * hash11(fi * 5.7), 0.20);
        dGyros = min(dGyros, dPlate);
    }

    // Luminous rings threaded on the spine (Material 2)
    float dRings = 1e5;
    for (int i = 0; i < 4; i++) {
        float fi = float(i);
        vec3 b = w;
        b.x -= -0.95 + fi * 0.63;
        b.yz *= rot2(t * 0.10 + fi);
        dRings = min(dRings, sdTorus(b, vec2(0.34 + 0.06 * sin(t * 0.5 + fi), 0.022 + 0.010 * beat)));
    }

    vec2 res = vec2(dSpine, 1.0);
    if (dGyros < res.x) res = vec2(dGyros, 4.0);
    if (dRings < res.x) res = vec2(dRings, 2.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 8 — "SHARD BLOOM"
// The hull shatters into a bloom of free-floating chrome shards that slowly
// orbit a small surviving core.
// -----------------------------------------------------------------------------
vec2 csSeqShardBloom(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;

    vec3 w = p - vec3(0.07 * sin(t * 0.055), 0.05 * cos(t * 0.065), 0.0);
    w.xz *= rot2(t * 0.07);

    // Small dense core
    float dCore = sdOctahedron(w, 0.42 + 0.08 * subBass + 0.05 * beat);

    // 16 shards on independent orbits
    float dShards = 1e5;
    for (int i = 0; i < 16; i++) {
        float fi = float(i);
        vec3 h = hash33(vec3(fi * 3.3, fi * 1.9, fi * 4.7));
        float ang = h.x * TAU + t * (0.10 + 0.06 * h.y);
        float el = asin(clamp(h.y * 2.0 - 1.0, -1.0, 1.0));
        float rad = 0.55 + 0.62 * h.z + 0.10 * bass;
        vec3 c = vec3(cos(ang) * cos(el), sin(el), sin(ang) * cos(el)) * rad;
        vec3 b = w - c;
        b.xy *= rot2(ang * 1.5 + t * 0.3);
        b.yz *= rot2(el + t * 0.22);
        float len = 0.30 + 0.34 * h.z + 0.10 * treble;
        dShards = min(dShards, sdFinBlade(b, len, 0.013, 0.075 + 0.055 * h.y, 0.18));
    }

    vec2 res = vec2(dCore, 2.0);
    if (dShards < res.x) res = vec2(dShards, 4.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 9 — "HULL STRATA"
// The vessel is revealed as a stack of horizontal strata, each plate sliding
// against its neighbours like geological layers in chrome.
// -----------------------------------------------------------------------------
vec2 csSeqHullStrata(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float bassPhase = u.audio2.y;

    vec3 w = p - vec3(0.06 * sin(t * 0.06), 0.05 * cos(t * 0.05), 0.0);
    w.xz *= rot2(t * 0.065);

    // Nine horizontal plates forming the hull silhouette
    float dStrata = 1e5;
    for (int i = 0; i < 9; i++) {
        float fi = float(i);
        float yy = (fi - 4.0) * 0.105;
        // Each stratum is displaced sideways on its own phase
        float slide = 0.20 * sin(t * 0.45 + fi * 0.7) + 0.10 * bassPhase * 0.1;
        // Outer strata are shorter, giving a lens-shaped stack
        float falloff = 1.0 - 0.055 * abs(fi - 4.0);
        vec3 b = w - vec3(slide * 0.35, yy, 0.0);
        float d = sdEllipsoidC(b, vec3((1.42 + 0.08 * subBass) * falloff, 0.048 + 0.012 * bass, 0.46 * falloff));
        dStrata = min(dStrata, d);
    }

    // Glowing seam light escaping between the strata (Material 2)
    float dGlow = sdEllipsoidC(w, vec3(1.05, 0.34 + 0.05 * beat, 0.30));
    dGlow += 0.020 * (0.4 + bass) * sin(w.y * 30.0 + t * 2.0);

    vec2 res = vec2(dStrata, 4.0);
    if (dGlow < res.x) res = vec2(dGlow, 2.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 10 — "TWIN VESSEL"
// Two vessels fly in tight formation, mirroring each other with a shared
// plasma tether strung between their noses.
// -----------------------------------------------------------------------------
vec2 csSeqTwinVessel(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float bassPhase = u.audio2.y;

    vec3 w = p - vec3(0.06 * sin(t * 0.05), 0.05 * cos(t * 0.06), 0.0);
    w.xz *= rot2(t * 0.06);

    float sep = 0.62 + 0.14 * sin(t * 0.5) + 0.10 * bass;

    float dHulls = 1e5;
    for (int i = 0; i < 2; i++) {
        float sgn = float(i) * 2.0 - 1.0;
        vec3 b = w - vec3(0.0, sgn * sep, 0.0);
        b.xz *= rot2(sgn * 0.12 * sin(t * 0.35 + bassPhase * 0.1));
        float d = sdEllipsoidC(b, vec3(1.28 + 0.07 * subBass, 0.24 + 0.03 * bass, 0.30));
        // Open each hull's seam so the interior reads
        d = max(d, -sdBox(b - vec3(0.08, 0.0, 0.0), vec3(0.70, 0.11, 0.46)));
        dHulls = min(dHulls, d);
    }

    // Shared plasma tether between the two noses (Material 2)
    float dTether = sdCapsule(w, vec3(0.30, sep, 0.0), vec3(0.30, -sep, 0.0), 0.030 + 0.014 * beat);
    dTether += 0.014 * (0.4 + mid) * sin(w.y * 14.0 + t * 2.2);

    // Fins sprouting outward on each hull
    float dFins = 1e5;
    for (int i = 0; i < 10; i++) {
        float fi = float(i);
        float sgn = mod(fi, 2.0) * 2.0 - 1.0;
        vec3 b = w - vec3(0.0, sgn * sep, 0.0);
        b.xy *= rot2(sgn * (0.65 + 0.25 * sin(t * 0.4 + fi)));
        b.x -= 0.35 - mod(fi, 5.0) * 0.20;
        dFins = min(dFins, sdFinBlade(b, 0.60 + 0.30 * hash11(fi * 3.1), 0.009, 0.09, 0.14));
    }

    vec2 res = vec2(dHulls, 1.0);
    if (dFins < res.x)   res = vec2(dFins, 4.0);
    if (dTether < res.x) res = vec2(dTether, 2.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 11 — "NOZZLE FLARE"
// A rear three-quarter view: the vessel's engine nozzle flares wide, venting a
// brilliant cone of plasma and embers.
// -----------------------------------------------------------------------------
vec2 csSeqNozzleFlare(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float bassPhase = u.audio2.y;

    vec3 w = p - vec3(0.05 * sin(t * 0.05), 0.04 * cos(t * 0.05), 0.0);
    w.yz *= rot2(t * 0.08);

    // Short foreshortened hull body
    float dHull = sdEllipsoidC(w - vec3(0.55, 0.0, 0.0), vec3(1.05 + 0.07 * subBass, 0.36 + 0.04 * bass, 0.40));

    // Nozzle bell opening toward -X
    vec3 b = w;
    b.xz *= rot2(0.0);
    float flare = 0.34 + 0.10 * beat + 0.06 * bass;
    float dNozzle = sdCylinder(b - vec3(-0.55, 0.0, 0.0), vec2(flare, 0.34));

    // Plasma cone venting out of the nozzle (Material 2)
    float dCone = 1e5;
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float along = -0.95 - fi * 0.22;
        float spread = 0.22 + fi * 0.085 + 0.06 * treble;
        float ang = fi * 1.7 + t * 0.5;
        vec3 c = vec3(along, cos(ang) * spread, sin(ang) * spread);
        float sz = 0.15 - fi * 0.011 + 0.02 * beat;
        dCone = min(dCone, sdEllipsoidC(w - c, vec3(sz * 1.7, sz, sz)));
    }

    // Nozzle fins around the bell
    float dFins = 1e5;
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float a = fi * 0.7854 + t * 0.10;
        vec3 f = w - vec3(-0.35, cos(a) * flare, sin(a) * flare);
        f.yz *= rot2(-a);
        f.xy *= rot2(0.55);
        dFins = min(dFins, sdFinBlade(f, 0.55 + 0.20 * hash11(fi * 2.7), 0.010, 0.10, 0.16));
    }

    vec2 res = vec2(dHull, 1.0);
    if (dNozzle < res.x) res = vec2(dNozzle, 4.0);
    if (dFins < res.x)   res = vec2(dFins, 4.0);
    if (dCone < res.x)   res = vec2(dCone, 2.0);
    return res;
}

// -----------------------------------------------------------------------------
// SEQUENCE 12 — "STORM COLLAPSE"
// Everything converges: the vessel's fins and beads are drawn inward in a slow
// implosion, the hull compressing into a single hot point.
// -----------------------------------------------------------------------------
vec2 csSeqStormCollapse(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float subBass = u.audio0.x, bass = u.audio0.y, mid = u.audio0.w;
    float treble = u.audio1.y, beat = u.audio2.x;
    float highPhase = u.audio2.w;

    // The whole scene breathes inward and outward
    float collapse = 1.0 - 0.22 * (0.5 + 0.5 * sin(t * 0.42)) - 0.12 * beat;
    vec3 w = (p - vec3(0.05 * sin(t * 0.06), 0.04 * cos(t * 0.05), 0.0)) / max(collapse, 0.45);
    w.xz *= rot2(t * 0.09 + highPhase * 0.04);

    // Compressed hull
    float dHull = sdEllipsoidC(w, vec3(0.95 + 0.06 * subBass, 0.26 + 0.04 * bass, 0.32));

    // Fins pulled inward, radiating around the compressed core
    float dFins = 1e5;
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        vec3 h = hash33(vec3(fi * 2.7, fi * 4.3, fi * 1.1));
        float ang = h.x * TAU + t * (0.18 + 0.10 * h.y);
        float el = asin(clamp(h.y * 2.0 - 1.0, -1.0, 1.0));
        vec3 dir = vec3(cos(ang) * cos(el), sin(el), sin(ang) * cos(el));
        vec3 c = dir * (0.55 + 0.55 * h.z);
        vec3 b = w - c;
        b.xy *= rot2(ang + t * 0.4);
        b.xz *= rot2(el);
        float len = 0.42 + 0.34 * h.z + 0.10 * treble;
        dFins = min(dFins, sdFinBlade(b, len, 0.010, 0.075 + 0.04 * h.y, 0.16));
    }

    // Hot compressed core at the centre (Material 2)
    float dCore = sdSphere(w, 0.22 + 0.07 * subBass + 0.05 * beat);
    dCore += 0.014 * (0.5 + bass) * sin(w.x * 12.0 + t * 2.4);

    vec2 res = vec2(dHull, 1.0);
    if (dFins < res.x) res = vec2(dFins, 4.0);
    if (dCore < res.x) res = vec2(dCore, 2.0);
    return res;
}

// Dispatch across the twelve CHROMATIC STORM sequences with weighted crossfades.
// Each form is held long enough to read, then eases into the next, and the last
// blend closes the loop back to the Furnace Hull with no visible pop.
vec2 csMapSequences(vec3 p) {
    float t = (u.preset.w > 0.001) ? u.preset.w : u.res.z;
    float cycle = fract(t * 0.0105);   // ~95 s for all twelve sequences

    // Twelve held states with eleven crossfades plus the closing blend.
    // Each hold is 0.0680 long, each crossfade 0.0227.
    float w[12];
    for (int i = 0; i < 12; i++) w[i] = 0.0;

    const float HOLD = 0.0680;
    const float FADE = 0.0227;
    const float SEG = HOLD + FADE;

    int seg = int(clamp(floor(cycle / SEG), 0.0, 11.0));
    float local = cycle - float(seg) * SEG;
    if (local <= HOLD) {
        w[seg] = 1.0;
    } else {
        float f = smoothstep(0.0, 1.0, (local - HOLD) / FADE);
        w[seg] = 1.0 - f;
        w[(seg + 1) % 12] = f;
    }

    vec2 seq[12];
    seq[0]  = csSeqFurnaceHull(p);
    seq[1]  = csSeqFinCascade(p);
    seq[2]  = csSeqSplitKeel(p);
    seq[3]  = csSeqBeadSurge(p);
    seq[4]  = csSeqEmberWake(p);
    seq[5]  = csSeqPlasmaCocoon(p);
    seq[6]  = csSeqSpineRing(p);
    seq[7]  = csSeqShardBloom(p);
    seq[8]  = csSeqHullStrata(p);
    seq[9]  = csSeqTwinVessel(p);
    seq[10] = csSeqNozzleFlare(p);
    seq[11] = csSeqStormCollapse(p);

    float dMix = 0.0;
    for (int i = 0; i < 12; i++) dMix += seq[i].x * w[i];

    // Material of whichever contributing sequence is nearest at this point
    float mat = 1.0;
    float best = 1e9;
    for (int i = 0; i < 12; i++) {
        if (w[i] > 0.02 && seq[i].x < best) { best = seq[i].x; mat = seq[i].y; }
    }

    // The bead trail and wire tails accompany every sequence
    float dTrail = csBeadTrail(p, t, 0.55, 1.0);
    if (dTrail < dMix) { dMix = dTrail; mat = 5.0; }
    float dWire = csWireTrail(p, t);
    if (dWire < dMix) { dMix = dWire; mat = 6.0; }
    return vec2(dMix, mat);
}

vec3 getPresetPalette(float t, vec2 uvHint) {
    if (u.preset.x > 9.5) {
        return chromaticStormPalette(t, uvHint);
    } else if (u.preset.x > 8.5) {
        return resonantFluidDynamicsPalette(t, uvHint);
    } else if (u.preset.x > 4.5) {
        float s = fract(t * 0.12 + uvHint.x * 0.16 + uvHint.y * 0.09);
        vec3 prismatic = mix(vec3(0.12, 0.82, 0.94), vec3(0.91, 0.20, 0.68), 0.5 + 0.5 * sin(s * TAU));
        vec3 pearl = mix(vec3(0.70, 0.75, 0.83), vec3(0.98, 0.98, 1.0), 0.5 + 0.5 * cos(s * TAU));
        return mix(pearl, prismatic, 0.48);
    } else if (u.preset.x > 3.5) {
        return sensoriumPalette(t, uvHint);
    } else if (u.preset.x > 2.5) {
        return infiniteComplexityPalette(t, uvHint);
    } else if (u.preset.x > 1.5) {
        return mplanetarianPalette(t, uvHint);
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

    if (u.preset.x > 9.5) {
        // =========================================================================
        // PRESET 11: DREAMWORLDS (CHROMATIC STORM)
        // Inspired by MPlanetarian_Dreamworlds_Lockscreen.png and the late
        // vessel sequence of XI-N / MPlanetarian "BIFURCATION (2026)".
        // Twelve animation sequences morph continuously:
        //   1  FURNACE HULL   — split teardrop hull with a molten core
        //   2  FIN CASCADE    — chrome fins fanning open along the hull
        //   3  SPLIT KEEL     — twin keels baring a plasma channel
        //   4  BEAD SURGE     — the bead swarm becomes the subject
        //   5  EMBER WAKE     — vessel coasting on a long fiery wake
        //   6  PLASMA COCOON  — luminous shell breathing around the hull
        //   7  SPINE RING     — bare skeleton spine with plate gyros
        //   8  SHARD BLOOM    — hull shattered into orbiting shards
        //   9  HULL STRATA    — hull revealed as sliding horizontal layers
        //  10  TWIN VESSEL    — mirrored pair with a plasma tether
        //  11  NOZZLE FLARE   — rear view, engine venting a plasma cone
        //  12  STORM COLLAPSE — everything implodes into a hot point
        // Every sequence carries the video's bead swarm and wire tails.
        // =========================================================================
        return csMapSequences(p);
    } else if (u.preset.x > 8.5) {
        // =========================================================================
        // PRESET 10: RESONANT FLUID DYNAMICS (MPlanetarian EARTH FLIPPER & DYNAMIC CORE)
        // Inspired by MPlanetarian's "Yaporigami - Earth Flipper (2022)" & Resonant Fluid Dynamics:
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
    } else if (u.preset.x > 4.5) {
        // BIFURCATION: a splitting chrome spindle with audio-driven fractured plates.
        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;
        vec3 q = p;
        q.xz *= rot2(dynTime * (0.08 + bass * 0.08));
        q.xy *= rot2(0.24 * sin(dynTime * 0.22 + midPhase));
        // A split double-prong body opens away from the center as the beat rises.
        vec3 leftProng = q - vec3(-0.43 - 0.15 * bass, 0.0, 0.0);
        leftProng.yz *= rot2(-0.20 - 0.10 * sin(dynTime * 0.4));
        vec3 rightProng = q - vec3(0.43 + 0.15 * bass, 0.0, 0.0);
        rightProng.yz *= rot2(0.20 + 0.10 * sin(dynTime * 0.4));
        float core = min(sdOctahedron(leftProng, 0.84 + 0.12 * subBass + 0.08 * beat),
                         sdOctahedron(rightProng, 0.84 + 0.12 * subBass + 0.08 * beat));
        float rings = sdTorus(q, vec2(1.48 + 0.16 * bass, 0.032 + 0.020 * beat));
        float shards = 1e4;
        for (int i = 0; i < 8; i++) {
            float a = float(i) * (TAU / 8.0) + dynTime * (0.12 + 0.05 * mid);
            vec3 s = q - vec3(cos(a) * 1.22, 0.0, sin(a) * 1.22);
            s.xy *= rot2(0.38 * sin(dynTime * 0.32 + a) + bassPhase * 0.10);
            s.yz *= rot2(a * 0.35);
            shards = min(shards, sdHexPrism(s, vec2(0.56 + 0.08 * treble, 0.055)));
        }
        vec2 result = vec2(core, 1.0);
        if (rings < result.x) result = vec2(rings, 2.0);
        if (shards < result.x) result = vec2(shards, 4.0);
        return result;
    } else if (u.preset.x > 3.5) {
        // --- PRESET 4: SENSORIUM INTERFACE (MPlanetarian EARTH FLIPPER CELESTIAL GYROSCOPE) ---
        // Inspired by MPlanetarian's "Yaporigami - Earth Flipper (2022)" and Sensorium_Interface.jpeg:
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
        // --- PRESET 3: INFINITE COMPLEXITY (MPlanetarian MIRRORED MADNESS) ---
        // Inspired by MPlanetarian's "Mirrored Madness" (Neo Shibuya 2023) and Cover_v4.png:
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

        // Really strange movements: MPlanetarian Mirrored Madness non-Euclidean space folding
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
        // MPlanetarian signature: 4 interwoven parametric tendrils snaking along the cyber-organism
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
        // --- PRESET 2: MPlanetarian XINRI D (KINETIC BIOMECH CYBER-ORIGAMI) ---
        // Inspired by MPlanetarian's XINRI D and Start_Menu_Icon.png:
        // 1. Central Biomechanical Aerodynamic Pod / Torpedo Engine (Frosted Pearlescent Liquid Glass)
        // 2. Twin High-Intensity Emissive Cyan Reactor Rings & Axial Drive Gimbals (Material 2)
        // 3. Swirling Helical Origami Sakura Ribbons & Tendrils wrapping the spine (Material 3)
        // 4. Floating Chrome Titanium Hexagon Armor Plates & MPlanetarian Tech Shards (Material 4)

        vec3 centerSpine = vec3(
            0.15 * sin(t * 0.28 + bassPhase * 0.15),
            0.10 * cos(t * 0.22 + midPhase * 0.12),
            0.0
        );

        // Biomechanical orientation: tilted in 3D space like MPlanetarian's composition
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
        float dHaloMPlanetarian = sdTorus(pHalo, vec2(3.10 + 0.22 * subBass, 0.035 + 0.02 * beat));
        float dRings = min(min(dRingA, dRingB), min(dRingC, dHaloMPlanetarian));

        // 3. Swirling Helical Origami Sakura Ribbons (Material 3: Pink Tendrils / Streamers)
        // MPlanetarian signature: 3 graceful helical streamers twisting along the main axis
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

        // 4. Floating Chrome Titanium Hexagon Armor Plates & MPlanetarian Origami Shards (Material 4)
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

    if (u.preset.x > 9.5) {
        // --- PRESET 11: DREAMWORLDS (CHROMATIC STORM) BACKGROUND ---
        // The lockscreen artwork is the total environment: a pale studio void
        // carrying the painting's iridescent arcs, heavy splatter and painterly
        // strokes, with a slow storm drift and beat-driven chromatic shear.
        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;

        // Bounded ray projection so the artwork never smears at grazing angles
        vec2 p3d = rd.xy / max(abs(rd.z) + 0.26, 0.32);
        p3d = clamp(p3d, -1.6, 1.6);
        float r3 = length(p3d);

        // Storm drift: the painted field rolls slowly like weather
        vec2 warpUv = p3d * 0.30;
        warpUv += vec2(
            sin(p3d.y * 2.1 + dynTime * 0.26 + bassPhase * 0.20),
            cos(p3d.x * 2.1 - dynTime * 0.22 + highPhase * 0.16)
        ) * (0.030 + 0.026 * bass);
        warpUv += vec2(
            sin(p3d.y * 1.1 - dynTime * 0.12),
            cos(p3d.x * 1.1 + dynTime * 0.10)
        ) * 0.020;

        vec2 baseUv = mix(mirrorUv(screenUv * 0.78 + 0.11), mirrorUv(warpUv + 0.5), 0.58);
        baseUv = mix(baseUv, mirrorUv(screenUv * 0.32 + 0.34), 0.24 + 0.08 * rms);

        // Chromatic shear, widening on beats — the "chromatic storm"
        float disp = 0.017 * (1.0 + 0.85 * beat);
        vec3 coverTex;
        coverTex.r = texture(uCoverTex, mirrorUv(baseUv + rd.xy * disp)).r;
        coverTex.g = texture(uCoverTex, mirrorUv(baseUv)).g;
        coverTex.b = texture(uCoverTex, mirrorUv(baseUv - rd.xy * disp)).b;

        // Keep the painting's pigment chemistry, lifting midtones so the chrome
        // hull always separates from the busy field
        float lumaBg = dot(coverTex, vec3(0.299, 0.587, 0.114));
        coverTex = mix(vec3(lumaBg), coverTex, 1.22);
        coverTex = clamp(coverTex * 1.04 + 0.02, 0.0, 1.0);

        // Pale studio falloff toward the frame edges, as in the vessel frames
        vec3 paleVoid = vec3(0.898, 0.906, 0.936);
        float vigBg = smoothstep(1.65, 0.28, r3);
        vec3 bg = mix(coverTex * 0.96, paleVoid, (1.0 - vigBg) * 0.26);
        bg *= (0.90 + 0.05 * rms);

        // Faint molten glow low in the frame, echoing the furnace light
        float furnaceGlow = exp(-abs(rd.y + 0.35) * 4.2);
        bg += vec3(1.0, 0.52, 0.11) * furnaceGlow * (0.030 + 0.028 * mid);

        // Airborne bead dust and fine wire motes catching the light
        vec3 dustP = rd * 12.0;
        dustP.xy += vec2(dynTime * 0.10, -dynTime * 0.07);
        float dust = pow(valueNoise3(dustP), 15.0) * (8.0 + 7.0 * treble);
        bg += vec3(0.32, 0.30, 0.36) * dust;

        return bg;
    }

    if (u.preset.x > 8.5) {
        // --- PRESET 10: RESONANT FLUID DYNAMICS (DYNAMIC CONTINUOUS COLOR-CHANGING BACKGROUND) ---
        // 3D ray-projected celestial fluid manifold with infinite complexity design (dreamworlds),
        // continuously evolving background color palette, MPlanetarian mirrored perspective grid,
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

        // Mirrored MPlanetarian perspective grid planes
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
        float stars = pow(valueNoise3(starP), 14.0) * (18.0 + 16.0 * treble);

        // Volumetric fluid fog & luminous aurora ripples
        float fluidAurora = 0.18 * sin(rd.x * 5.0 + rd.y * 4.0 + dynTime * 0.6 + bassPhase * 0.4);
        fluidAurora += 0.12 * cos(rd.x * 9.0 - rd.y * 7.0 - dynTime * 0.45);
        fluidAurora = clamp(fluidAurora, 0.0, 1.0) * (0.65 + 0.55 * mid);

        vec3 bgFinal = colDeepSpace + coverTex * (0.42 + 0.25 * rms)
            + vec3(0.290, 0.867, 0.647) * gridLines
            + vec3(0.965, 0.592, 0.722) * fluidAurora
            + vec3(0.902, 0.945, 0.820) * stars;

        return bgFinal;
    } else if (u.preset.x > 4.5) {
        float dynTime = (u.preset.w > 0.001) ? u.preset.w : t;
        vec2 p3d = rd.xy / (abs(rd.z) + 0.11);
        float angle = atan(p3d.y, p3d.x);
        float fracture = abs(sin(angle * 18.0 + dynTime * 0.11 + bassPhase * 0.2));
        float shards = smoothstep(0.92, 1.0, fracture) * (0.35 + 0.55 * treble);
        float dust = pow(hash21(floor(p3d * 34.0 + dynTime * 0.08)), 24.0) * (1.0 + 2.0 * treble);
        vec2 uv = p3d * 0.25 + 0.5 + 0.035 * vec2(sin(angle * 5.0 + dynTime * 0.2), cos(angle * 7.0 - dynTime * 0.17));
        vec3 cover = texture(uCoverTex, mirrorUv(uv)).rgb;
        vec3 pale = mix(vec3(0.72, 0.76, 0.84), vec3(0.94, 0.94, 0.98), 0.5 + 0.5 * sin(angle * 4.0 + dynTime * 0.12));
        vec3 prism = vec3(0.10, 0.82, 0.92) * (0.5 + 0.5 * sin(angle * 9.0 - dynTime * 0.2))
                   + vec3(0.95, 0.18, 0.62) * (0.5 + 0.5 * cos(angle * 7.0 + dynTime * 0.18));
        return mix(pale, cover, 0.52) + prism * (0.12 + 0.28 * shards) + vec3(0.42, 0.48, 0.58) * dust;
    } else if (u.preset.x > 3.5) {
        // --- PRESET 4: SENSORIUM INTERFACE (MPlanetarian EARTH FLIPPER CELESTIAL BACKGROUND) ---
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
        // chromatic dispersion, MPlanetarian mirrored lattice grid, and floating quantum starlight.
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

        // 3D MPlanetarian Mirrored Lattice grid receding into perspective depth
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
        // --- PRESET 2: MPlanetarian XINRI D BACKGROUND ---
        // Clean high-tech cyber atmosphere inspired by MPlanetarian's minimalist gradient sky
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
                vec3 splatCol = mplanetarianPalette(h + fl * 0.22 + t * 0.04, mirrorUv(screenUv));
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
    bool isChromaticStorm = (u.preset.x > 9.5);
    float baseCamDist = isChromaticStorm ? 4.95 : ((u.preset.x > 8.5) ? 5.35 : ((u.preset.x > 7.5) ? 5.30 : ((u.preset.x > 6.5) ? 5.10 : ((u.preset.x > 5.5) ? 5.15 : ((u.preset.x > 3.5) ? 5.20 : ((u.preset.x > 2.5) ? 5.25 : ((u.preset.x > 1.5) ? 5.10 : 4.35)))))));
    float camDist = baseCamDist - 0.45 * bass - 0.22 * beat + 0.35 * sin(t * 0.19);
    float camYaw = t * 0.16 + 0.25 * sin(t * 0.11 + bassPhase * 0.08);
    float camPitch = 0.18 * sin(t * 0.14 + midPhase * 0.06);

    if (isChromaticStorm) {
        // The reference shots orbit the vessel broadside and slightly below,
        // with occasional slow three-quarter passes. Per-sequence framing keeps
        // every form readable inside the square window.
        float csCycle = fract(t * 0.0105);
        const float CS_SEG = 0.0680 + 0.0227;
        int csSeg = int(clamp(floor(csCycle / CS_SEG), 0.0, 11.0));

        // wider shots for the formations that spread out or run long
        float wide = 0.0;
        if (csSeg == 1) wide = -0.55;  // fin cascade
        if (csSeg == 2) wide = -0.75;  // split keel
        if (csSeg == 3) wide = 0.55;   // bead surge (wide river)
        if (csSeg == 4) wide = -0.15;  // ember wake
        if (csSeg == 5) wide = -0.20;  // plasma cocoon
        if (csSeg == 6) wide = -0.55;  // spine ring
        if (csSeg == 7) wide = -0.40;  // shard bloom
        if (csSeg == 8) wide = -0.30;  // hull strata
        if (csSeg == 9) wide = 0.45;   // twin vessel
        if (csSeg == 10) wide = 0.30;  // nozzle flare
        if (csSeg == 11) wide = -0.85; // storm collapse

        // A fixed per-sequence yaw offset guarantees each form is seen from a
        // three-quarter angle. Without it the slow orbit can drift to a purely
        // axial view and the vessels read as flat discs.
        float yawBias = 0.0;
        if (csSeg == 0) yawBias = 0.95;   // furnace hull
        if (csSeg == 2) yawBias = 1.25;   // split keel
        if (csSeg == 4) yawBias = 1.55;   // ember wake
        if (csSeg == 9) yawBias = 1.15;   // twin vessel
        if (csSeg == 10) yawBias = 2.30;  // nozzle flare (rear three-quarter)
        if (csSeg == 11) yawBias = 0.85;  // storm collapse

        camDist = 5.05 - 0.33 * bass - 0.16 * beat + 0.16 * sin(t * 0.11) + wide;
        camYaw = t * 0.085 + 0.26 * sin(t * 0.05 + bassPhase * 0.05) + yawBias;
        camPitch = 0.10 * sin(t * 0.065 + midPhase * 0.04) + 0.06 * sin(t * 0.021);
    }

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

        if (isChromaticStorm) {
            // =====================================================================
            // CHROMATIC STORM material set, resolved up front so the legacy
            // preset chain below is left completely untouched.
            //   1.0 Dark anodised hull plate
            //   2.0 Molten furnace / plasma emission
            //   3.0 Hot ember wake
            //   4.0 Polished chrome fin
            //   5.0 Matte black perforated bead
            //   6.0 Graphite wire tail
            // =====================================================================
            float specKey = pow(max(dot(reflect(-lightDir1, n), v), 0.0), 58.0);
            float specRim = pow(max(dot(reflect(-lightDir2, n), v), 0.0), 24.0);

            if (matId == 2.0 || matId == 3.0) {
                // --- Molten furnace / plasma / ember emission ---
                // Self-luminous: brightness comes from within, with hue shifting
                // from deep crimson at the core to white-hot at grazing angles.
                float heat = clamp(pow(max(dot(n, v), 0.0), 1.2), 0.0, 1.0);
                vec3 hot = mix(vec3(1.000, 0.520, 0.110), vec3(1.000, 0.930, 0.760), heat);
                hot = mix(vec3(0.960, 0.180, 0.140), hot, 0.35 + 0.55 * heat);
                if (matId == 3.0) {
                    // Ember wake cools toward crimson as it trails away
                    hot = mix(vec3(0.960, 0.240, 0.120), hot, 0.55);
                }
                col = hot * (0.72 + 0.55 * heat) * (0.80 + 0.30 * beat)
                    + hot * fresnel * 0.65
                    + vec3(1.0, 0.985, 0.95) * specKey * 0.45;

            } else if (matId == 5.0) {
                // --- Matte black perforated bead ---
                float sheen = pow(max(dot(n, lightDir1), 0.0), 2.0);
                col = vec3(0.026, 0.024, 0.032) * (0.75 + 0.55 * ao)
                    + vec3(0.40, 0.41, 0.46) * sheen * 0.32
                    + vec3(0.60, 0.58, 0.64) * specKey * 0.28;

            } else if (matId == 6.0) {
                // --- Graphite wire tail ---
                col = vec3(0.042, 0.045, 0.058) * (0.9 + 0.4 * ao)
                    + vec3(0.28, 0.29, 0.34) * pow(max(dot(n, lightDir1), 0.0), 3.0) * 0.30;

            } else if (matId == 4.0) {
                // --- Polished chrome fin ---
                // Bright brushed metal that mirrors the pale void, with a hard
                // crease highlight and a faint chromatic fringe on the edges.
                vec3 env = texture(uCoverTex, mirrorUv(screenUv + reflect(rd, n).xy * 0.22)).rgb;
                float brush = 0.5 + 0.5 * sin(p.x * 20.0 + p.z * 13.0 + t * 0.7);
                vec3 chrome = mix(vec3(0.46, 0.49, 0.56), env, 0.34 + 0.26 * fresnel);
                vec3 fringe = mix(vec3(0.960, 0.180, 0.780), vec3(0.180, 0.860, 1.000),
                                  0.5 + 0.5 * sin(n.y * 4.5 + t * 0.6));
                col = chrome * (0.70 + 0.50 * diff1) * (0.62 + 0.40 * ao)
                    + env * 0.14 * (0.5 + 0.5 * n.y)
                    + fringe * fresnel * (0.42 + 0.30 * treble)
                    + vec3(1.0, 0.99, 0.98) * pow(max(dot(reflect(-lightDir1, n), v), 0.0), 46.0 + 24.0 * brush) * (0.85 + 0.40 * beat)
                    + vec3(0.960, 0.180, 0.780) * specRim * 0.14;

            } else {
                // --- Dark anodised hull plate ---
                // Deep graphite metal with a cool rim, so the chrome fins and
                // the molten core both read clearly against it.
                vec3 env = texture(uCoverTex, mirrorUv(screenUv + reflect(rd, n).xy * 0.18)).rgb;
                vec3 hull = mix(vec3(0.062, 0.068, 0.086), env, 0.22 + 0.20 * fresnel);
                col = hull * (0.50 + 0.58 * diff1) * (0.55 + 0.45 * ao)
                    + vec3(0.180, 0.860, 1.000) * fresnel * (0.35 + 0.25 * rms)
                    + vec3(0.96, 0.97, 1.00) * specKey * (0.80 + 0.40 * beat)
                    + vec3(1.000, 0.520, 0.110) * specRim * 0.16;
            }

            float fogCs = smoothstep(6.4, tMax, dist);
            col = mix(col, bgCol, fogCs);
        } else if (matId == 1.0) {
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
            float innerCaust = valueNoise3(p * 3.8 + vec3(t * 0.45, -bassPhase * 0.3, midPhase * 0.25));
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
            if (u.preset.x > 4.5) {
                vec3 chrome = mix(vec3(0.48, 0.56, 0.68), vec3(0.96, 0.98, 1.0), 0.35 + 0.65 * diff1);
                vec3 splitPrism = mix(vec3(0.03, 0.88, 1.0), vec3(1.0, 0.12, 0.62), 0.5 + 0.5 * sin(p.x * 5.0 + t * 0.25));
                col = chrome * (0.42 + 0.48 * ao) + splitPrism * (0.32 + fresnel * 1.25)
                    + vec3(1.0) * spec1 * (2.4 + beat);
            }

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
            } else if (u.preset.x > 4.5) {
                ringBase = mix(vec3(0.02, 0.82, 1.0), vec3(1.0, 0.10, 0.58), 0.5 + 0.5 * ringWave);
                ringBase = mix(ringBase, vec3(0.94, 0.98, 1.0), smoothstep(0.25, 0.9, sin(p.x * 11.0 + t * 1.7)));
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
            if (u.preset.x > 4.5) {
                float facetPulse = 0.5 + 0.5 * sin(dot(p, vec3(3.0, 5.0, 7.0)) + t * 0.6 + highPhase);
                vec3 chromeFacet = mix(vec3(0.38, 0.45, 0.58), vec3(0.96, 0.98, 1.0), facetPulse);
                col = chromeFacet * (0.5 + 0.5 * ao) + edgeGlow * (0.35 + 0.95 * fresnel)
                    + vec3(0.85, 0.95, 1.0) * spec * 2.0;
            }
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
