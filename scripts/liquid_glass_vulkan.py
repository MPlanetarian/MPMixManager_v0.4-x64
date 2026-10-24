"""NVIDIA Vulkan liquid-glass window.

The glass is drawn with libvulkan on the NVIDIA discrete GPU. llvmpipe and
other devices are refused. GLFW supplies the X11 window and the VkSurface.

NVIDIA's X11 swapchain is opaque, so the clear pane is KWin's blur and
window opacity over a light frost drawn by the shader.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import (
    CFUNCTYPE,
    POINTER,
    byref,
    c_char,
    c_char_p,
    c_double,
    c_float,
    c_int,
    c_int32,
    c_size_t,
    c_uint8,
    c_uint32,
    c_uint64,
    c_void_p,
)
from pathlib import Path

NVIDIA_VENDOR_ID = 0x10DE
DISCRETE_GPU = 2

ROOT = Path(__file__).resolve().parent.parent
SHADER_DIR = ROOT / "shaders"

THEME_COLORS = {
    "dreamworlds_ultra": ((166, 77, 255), (247, 37, 133), (0, 229, 255)),
    "cosmic_supernova": ((224, 86, 253), (0, 245, 212), (76, 201, 240)),
    "dreamworlds_neon": ((0, 229, 255), (247, 37, 133), (102, 102, 255)),
    "retro_studio": ((241, 196, 15), (230, 126, 34), (243, 156, 18)),
    "cyber_neon": ((76, 201, 240), (255, 0, 85), (153, 153, 255)),
    "phosphor": ((57, 255, 20), (166, 255, 0), (0, 255, 102)),
    "ice_cold": ((0, 229, 255), (136, 192, 208), (129, 161, 193)),
    "retro_terminal": ((230, 230, 230), (180, 180, 180), (255, 255, 255)),
}
THEME_ALIASES = {
    "dreamworlds": "dreamworlds_ultra",
    "default": "dreamworlds_ultra",
    "mplanetarian": "dreamworlds_ultra",
    "cosmic": "cosmic_supernova",
    "supernova": "cosmic_supernova",
    "cyberpunk": "cyber_neon",
    "cyber": "cyber_neon",
    "matrix": "phosphor",
    "nord": "ice_cold",
    "dracula": "dreamworlds_neon",
    "gruvbox": "retro_studio",
    "unix_terminal": "retro_terminal",
    "terminal": "retro_terminal",
    "classic": "retro_terminal",
}


def select_nvidia_device(devices):
    """Pick the NVIDIA discrete GPU. devices are dicts with vendor_id, device_type, name."""
    nvidia = [i for i, dev in enumerate(devices) if int(dev["vendor_id"]) == NVIDIA_VENDOR_ID]
    if not nvidia:
        seen = ", ".join(str(dev.get("name") or "unknown") for dev in devices) or "none"
        raise RuntimeError(
            "Liquid Glass requires the NVIDIA Vulkan API. "
            f"No NVIDIA device was found (saw: {seen})."
        )
    discrete = [i for i in nvidia if int(devices[i].get("device_type", -1)) == DISCRETE_GPU]
    return (discrete or nvidia)[0]


def theme_rgb(name):
    key = THEME_ALIASES.get(str(name or "").strip().lower(), str(name or "").strip().lower())
    return THEME_COLORS.get(key, THEME_COLORS["dreamworlds_ultra"])


def read_player_theme(config_dir=None):
    path = Path(config_dir) if config_dir else Path.home() / ".config" / "mix-manager"
    theme_file = path / "theme"
    try:
        name = theme_file.read_text(encoding="utf-8").strip().lower()
    except OSError:
        name = "dreamworlds_ultra"
    return name or "dreamworlds_ultra"


def _rgb01(rgb):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


# Vulkan structure types and flags used by this renderer.
ST_APPLICATION_INFO = 0
ST_INSTANCE_CREATE_INFO = 1
ST_DEVICE_QUEUE_CREATE_INFO = 2
ST_DEVICE_CREATE_INFO = 3
ST_SUBMIT_INFO = 4
ST_MEMORY_ALLOCATE_INFO = 5
ST_FENCE_CREATE_INFO = 8
ST_SEMAPHORE_CREATE_INFO = 9
ST_BUFFER_CREATE_INFO = 12
ST_IMAGE_VIEW_CREATE_INFO = 15
ST_SHADER_MODULE_CREATE_INFO = 16
ST_PIPELINE_SHADER_STAGE = 18
ST_PIPELINE_VERTEX_INPUT = 19
ST_PIPELINE_INPUT_ASSEMBLY = 20
ST_PIPELINE_VIEWPORT = 22
ST_PIPELINE_RASTER = 23
ST_PIPELINE_MULTISAMPLE = 24
ST_PIPELINE_COLOR_BLEND = 26
ST_PIPELINE_DYNAMIC = 27
ST_GRAPHICS_PIPELINE = 28
ST_PIPELINE_LAYOUT = 30
ST_DESCRIPTOR_SET_LAYOUT = 32
ST_DESCRIPTOR_POOL = 33
ST_DESCRIPTOR_SET_ALLOCATE = 34
ST_WRITE_DESCRIPTOR_SET = 35
ST_FRAMEBUFFER = 37
ST_RENDER_PASS = 38
ST_COMMAND_POOL = 39
ST_COMMAND_BUFFER_ALLOCATE = 40
ST_COMMAND_BUFFER_BEGIN = 42
ST_RENDER_PASS_BEGIN = 43
ST_BUFFER_MEMORY_BARRIER = 44
ST_IMAGE_MEMORY_BARRIER = 45
ST_SWAPCHAIN_CREATE = 1000001000
ST_PRESENT_INFO = 1000001001

QUEUE_GRAPHICS = 0x1
IMAGE_USAGE_TRANSFER_SRC = 0x1
IMAGE_USAGE_COLOR = 0x10
SHARING_EXCLUSIVE = 0
COMPOSITE_OPAQUE = 0x1
COMPOSITE_PRE = 0x2
COMPOSITE_POST = 0x4
COMPOSITE_INHERIT = 0x8
PRESENT_FIFO = 2
TRANSFORM_IDENTITY = 0x1
FORMAT_R8G8B8A8_UNORM = 37
FORMAT_B8G8R8A8_UNORM = 44
FORMAT_B8G8R8A8_SRGB = 50
COLORSPACE_SRGB = 0
IMAGE_VIEW_2D = 1
IMAGE_ASPECT_COLOR = 0x1
SAMPLE_1 = 0x1
LOAD_CLEAR = 1
STORE_STORE = 0
STORE_DONT = 1
LOAD_DONT = 2
LAYOUT_UNDEFINED = 0
LAYOUT_COLOR = 2
LAYOUT_TRANSFER_SRC = 6
LAYOUT_PRESENT = 1000001002
SUBPASS_EXTERNAL = 0xFFFFFFFF
STAGE_FRAGMENT = 0x80
STAGE_COLOR_OUT = 0x400
STAGE_TRANSFER = 0x1000
STAGE_BOTTOM = 0x2000
STAGE_HOST = 0x4000
ACCESS_UNIFORM = 0x8
ACCESS_COLOR_WRITE = 0x100
ACCESS_TRANSFER_READ = 0x800
ACCESS_HOST_WRITE = 0x4000
ACCESS_MEMORY_READ = 0x8000
CMD_POOL_RESET = 0x2
CMD_ONE_TIME = 0x1
FENCE_SIGNALED = 0x1
TOPOLOGY_TRIANGLE_LIST = 3
BLEND_ONE = 1
BLEND_ONE_MINUS_SRC_ALPHA = 7
BLEND_ADD = 0
COLOR_WRITE_ALL = 0xF
DYNAMIC_VIEWPORT = 0
DYNAMIC_SCISSOR = 1
DESCRIPTOR_UNIFORM = 6
SHADER_VERTEX = 0x1
SHADER_FRAGMENT = 0x10
STAGE_VERTEX_BIT = 0x00000001
STAGE_FRAGMENT_BIT = 0x00000010
MEMORY_HOST_VISIBLE = 0x2
MEMORY_HOST_COHERENT = 0x4
QUEUE_FAMILY_IGNORED = 0xFFFFFFFF
SUBOPTIMAL = 1000001003
OUT_OF_DATE = -1000001004
WHOLE_SIZE = 0xFFFFFFFFFFFFFFFF
SUCCESS = 0

GLFW_CLIENT_API = 0x00022001
GLFW_NO_API = 0
GLFW_RESIZABLE = 0x00020003
GLFW_VISIBLE = 0x00020004
GLFW_DECORATED = 0x00020005
GLFW_FOCUSED = 0x00020001
GLFW_FOCUS_ON_SHOW = 0x0002000C
GLFW_TRANSPARENT = 0x0002000A
GLFW_PLATFORM = 0x00050003
GLFW_PLATFORM_X11 = 0x00060004
GLFW_TRUE = 1
GLFW_FALSE = 0
GLFW_PRESS = 1


class VkApplicationInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("pApplicationName", c_char_p),
        ("applicationVersion", c_uint32), ("pEngineName", c_char_p),
        ("engineVersion", c_uint32), ("apiVersion", c_uint32),
    ]


class VkInstanceCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("pApplicationInfo", c_void_p), ("enabledLayerCount", c_uint32),
        ("ppEnabledLayerNames", c_void_p), ("enabledExtensionCount", c_uint32),
        ("ppEnabledExtensionNames", c_void_p),
    ]


class VkDeviceQueueCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("queueFamilyIndex", c_uint32), ("queueCount", c_uint32),
        ("pQueuePriorities", c_void_p),
    ]


class VkDeviceCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("queueCreateInfoCount", c_uint32), ("pQueueCreateInfos", c_void_p),
        ("enabledLayerCount", c_uint32), ("ppEnabledLayerNames", c_void_p),
        ("enabledExtensionCount", c_uint32), ("ppEnabledExtensionNames", c_void_p),
        ("pEnabledFeatures", c_void_p),
    ]


class VkExtent2D(ctypes.Structure):
    _fields_ = [("width", c_uint32), ("height", c_uint32)]


class VkExtent3D(ctypes.Structure):
    _fields_ = [("width", c_uint32), ("height", c_uint32), ("depth", c_uint32)]


class VkOffset2D(ctypes.Structure):
    _fields_ = [("x", c_int32), ("y", c_int32)]


class VkOffset3D(ctypes.Structure):
    _fields_ = [("x", c_int32), ("y", c_int32), ("z", c_int32)]


class VkRect2D(ctypes.Structure):
    _fields_ = [("offset", VkOffset2D), ("extent", VkExtent2D)]


class VkSurfaceCapabilitiesKHR(ctypes.Structure):
    _fields_ = [
        ("minImageCount", c_uint32), ("maxImageCount", c_uint32),
        ("currentExtent", VkExtent2D), ("minImageExtent", VkExtent2D),
        ("maxImageExtent", VkExtent2D), ("maxImageArrayLayers", c_uint32),
        ("supportedTransforms", c_uint32), ("currentTransform", c_uint32),
        ("supportedCompositeAlpha", c_uint32), ("supportedUsageFlags", c_uint32),
    ]


class VkSurfaceFormatKHR(ctypes.Structure):
    _fields_ = [("format", c_uint32), ("colorSpace", c_uint32)]


class VkSwapchainCreateInfoKHR(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("surface", c_uint64), ("minImageCount", c_uint32), ("imageFormat", c_uint32),
        ("imageColorSpace", c_uint32), ("imageExtent", VkExtent2D),
        ("imageArrayLayers", c_uint32), ("imageUsage", c_uint32),
        ("imageSharingMode", c_uint32), ("queueFamilyIndexCount", c_uint32),
        ("pQueueFamilyIndices", c_void_p), ("preTransform", c_uint32),
        ("compositeAlpha", c_uint32), ("presentMode", c_uint32),
        ("clipped", c_uint32), ("oldSwapchain", c_uint64),
    ]


class VkImageViewCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("image", c_uint64), ("viewType", c_uint32), ("format", c_uint32),
        ("r", c_uint32), ("g", c_uint32), ("b", c_uint32), ("a", c_uint32),
        ("aspectMask", c_uint32), ("baseMipLevel", c_uint32), ("levelCount", c_uint32),
        ("baseArrayLayer", c_uint32), ("layerCount", c_uint32),
    ]


class VkAttachmentDescription(ctypes.Structure):
    _fields_ = [
        ("flags", c_uint32), ("format", c_uint32), ("samples", c_uint32),
        ("loadOp", c_uint32), ("storeOp", c_uint32),
        ("stencilLoadOp", c_uint32), ("stencilStoreOp", c_uint32),
        ("initialLayout", c_uint32), ("finalLayout", c_uint32),
    ]


class VkAttachmentReference(ctypes.Structure):
    _fields_ = [("attachment", c_uint32), ("layout", c_uint32)]


class VkSubpassDescription(ctypes.Structure):
    _fields_ = [
        ("flags", c_uint32), ("pipelineBindPoint", c_uint32),
        ("inputAttachmentCount", c_uint32), ("pInputAttachments", c_void_p),
        ("colorAttachmentCount", c_uint32), ("pColorAttachments", c_void_p),
        ("pResolveAttachments", c_void_p), ("pDepthStencilAttachment", c_void_p),
        ("preserveAttachmentCount", c_uint32), ("pPreserveAttachments", c_void_p),
    ]


class VkSubpassDependency(ctypes.Structure):
    _fields_ = [
        ("srcSubpass", c_uint32), ("dstSubpass", c_uint32),
        ("srcStageMask", c_uint32), ("dstStageMask", c_uint32),
        ("srcAccessMask", c_uint32), ("dstAccessMask", c_uint32),
        ("dependencyFlags", c_uint32),
    ]


class VkRenderPassCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("attachmentCount", c_uint32), ("pAttachments", c_void_p),
        ("subpassCount", c_uint32), ("pSubpasses", c_void_p),
        ("dependencyCount", c_uint32), ("pDependencies", c_void_p),
    ]


class VkFramebufferCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("renderPass", c_uint64), ("attachmentCount", c_uint32),
        ("pAttachments", c_void_p), ("width", c_uint32), ("height", c_uint32),
        ("layers", c_uint32),
    ]


class VkShaderModuleCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("codeSize", c_size_t), ("pCode", c_void_p),
    ]


class VkPipelineShaderStageCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("stage", c_uint32), ("module", c_uint64), ("pName", c_char_p),
        ("pSpecializationInfo", c_void_p),
    ]


class VkVertexInputBindingDescription(ctypes.Structure):
    _fields_ = [("binding", c_uint32), ("stride", c_uint32), ("inputRate", c_uint32)]


class VkVertexInputAttributeDescription(ctypes.Structure):
    _fields_ = [("location", c_uint32), ("binding", c_uint32), ("format", c_uint32), ("offset", c_uint32)]


class VkPipelineVertexInputStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("vertexBindingDescriptionCount", c_uint32), ("pVertexBindingDescriptions", c_void_p),
        ("vertexAttributeDescriptionCount", c_uint32), ("pVertexAttributeDescriptions", c_void_p),
    ]


class VkPipelineInputAssemblyStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("topology", c_uint32), ("primitiveRestartEnable", c_uint32),
    ]


class VkPipelineViewportStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("viewportCount", c_uint32), ("pViewports", c_void_p),
        ("scissorCount", c_uint32), ("pScissors", c_void_p),
    ]


class VkPipelineRasterizationStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("depthClampEnable", c_uint32), ("rasterizerDiscardEnable", c_uint32),
        ("polygonMode", c_uint32), ("cullMode", c_uint32), ("frontFace", c_uint32),
        ("depthBiasEnable", c_uint32), ("depthBiasConstantFactor", c_float),
        ("depthBiasClamp", c_float), ("depthBiasSlopeFactor", c_float),
        ("lineWidth", c_float),
    ]


class VkPipelineMultisampleStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("rasterizationSamples", c_uint32), ("sampleShadingEnable", c_uint32),
        ("minSampleShading", c_float), ("pSampleMask", c_void_p),
        ("alphaToCoverageEnable", c_uint32), ("alphaToOneEnable", c_uint32),
    ]


class VkPipelineColorBlendAttachmentState(ctypes.Structure):
    _fields_ = [
        ("blendEnable", c_uint32), ("srcColorBlendFactor", c_uint32),
        ("dstColorBlendFactor", c_uint32), ("colorBlendOp", c_uint32),
        ("srcAlphaBlendFactor", c_uint32), ("dstAlphaBlendFactor", c_uint32),
        ("alphaBlendOp", c_uint32), ("colorWriteMask", c_uint32),
    ]


class VkPipelineColorBlendStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("logicOpEnable", c_uint32), ("logicOp", c_uint32),
        ("attachmentCount", c_uint32), ("pAttachments", c_void_p),
        ("blendConstants", c_float * 4),
    ]


class VkPipelineDynamicStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("dynamicStateCount", c_uint32), ("pDynamicStates", c_void_p),
    ]


class VkPipelineLayoutCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("setLayoutCount", c_uint32), ("pSetLayouts", c_void_p),
        ("pushConstantRangeCount", c_uint32), ("pPushConstantRanges", c_void_p),
    ]


class VkGraphicsPipelineCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("stageCount", c_uint32), ("pStages", c_void_p),
        ("pVertexInputState", c_void_p), ("pInputAssemblyState", c_void_p),
        ("pTessellationState", c_void_p), ("pViewportState", c_void_p),
        ("pRasterizationState", c_void_p), ("pMultisampleState", c_void_p),
        ("pDepthStencilState", c_void_p), ("pColorBlendState", c_void_p),
        ("pDynamicState", c_void_p), ("layout", c_uint64), ("renderPass", c_uint64),
        ("subpass", c_uint32), ("basePipelineHandle", c_uint64),
        ("basePipelineIndex", c_int32),
    ]


class VkDescriptorSetLayoutBinding(ctypes.Structure):
    _fields_ = [
        ("binding", c_uint32), ("descriptorType", c_uint32),
        ("descriptorCount", c_uint32), ("stageFlags", c_uint32),
        ("pImmutableSamplers", c_void_p),
    ]


class VkDescriptorSetLayoutCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("bindingCount", c_uint32), ("pBindings", c_void_p),
    ]


class VkDescriptorPoolSize(ctypes.Structure):
    _fields_ = [("type", c_uint32), ("descriptorCount", c_uint32)]


class VkDescriptorPoolCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("maxSets", c_uint32), ("poolSizeCount", c_uint32), ("pPoolSizes", c_void_p),
    ]


class VkDescriptorSetAllocateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("descriptorPool", c_uint64),
        ("descriptorSetCount", c_uint32), ("pSetLayouts", c_void_p),
    ]


class VkDescriptorBufferInfo(ctypes.Structure):
    _fields_ = [("buffer", c_uint64), ("offset", c_uint64), ("range", c_uint64)]


class VkWriteDescriptorSet(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("dstSet", c_uint64),
        ("dstBinding", c_uint32), ("dstArrayElement", c_uint32),
        ("descriptorCount", c_uint32), ("descriptorType", c_uint32),
        ("pImageInfo", c_void_p), ("pBufferInfo", c_void_p),
        ("pTexelBufferView", c_void_p),
    ]


class VkBufferCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("size", c_uint64), ("usage", c_uint32), ("sharingMode", c_uint32),
        ("queueFamilyIndexCount", c_uint32), ("pQueueFamilyIndices", c_void_p),
    ]


class VkMemoryAllocateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("allocationSize", c_uint64), ("memoryTypeIndex", c_uint32),
    ]


class VkMemoryRequirements(ctypes.Structure):
    _fields_ = [
        ("size", c_uint64), ("alignment", c_uint64), ("memoryTypeBits", c_uint32),
    ]


class VkMemoryType(ctypes.Structure):
    _fields_ = [("propertyFlags", c_uint32), ("heapIndex", c_uint32)]


class VkMemoryHeap(ctypes.Structure):
    _fields_ = [("size", c_uint64), ("flags", c_uint32), ("_pad", c_uint32)]


class VkPhysicalDeviceMemoryProperties(ctypes.Structure):
    _fields_ = [
        ("memoryTypeCount", c_uint32),
        ("memoryTypes", VkMemoryType * 32),
        ("memoryHeapCount", c_uint32),
        ("memoryHeaps", VkMemoryHeap * 16),
    ]


class VkQueueFamilyProperties(ctypes.Structure):
    _fields_ = [
        ("queueFlags", c_uint32), ("queueCount", c_uint32),
        ("timestampValidBits", c_uint32), ("minImageTransferGranularity", VkExtent3D),
    ]


class VkCommandPoolCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("queueFamilyIndex", c_uint32),
    ]


class VkCommandBufferAllocateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("commandPool", c_uint64),
        ("level", c_uint32), ("commandBufferCount", c_uint32),
    ]


class VkCommandBufferBeginInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("pInheritanceInfo", c_void_p),
    ]


class VkClearValue(ctypes.Structure):
    _fields_ = [("color", c_float * 4)]


class VkRenderPassBeginInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("renderPass", c_uint64),
        ("framebuffer", c_uint64), ("renderArea", VkRect2D),
        ("clearValueCount", c_uint32), ("pClearValues", c_void_p),
    ]


class VkViewport(ctypes.Structure):
    _fields_ = [
        ("x", c_float), ("y", c_float), ("width", c_float), ("height", c_float),
        ("minDepth", c_float), ("maxDepth", c_float),
    ]


class VkSubmitInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("waitSemaphoreCount", c_uint32), ("pWaitSemaphores", c_void_p),
        ("pWaitDstStageMask", c_void_p), ("commandBufferCount", c_uint32),
        ("pCommandBuffers", c_void_p), ("signalSemaphoreCount", c_uint32),
        ("pSignalSemaphores", c_void_p),
    ]


class VkPresentInfoKHR(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("waitSemaphoreCount", c_uint32), ("pWaitSemaphores", c_void_p),
        ("swapchainCount", c_uint32), ("pSwapchains", c_void_p),
        ("pImageIndices", c_void_p), ("pResults", c_void_p),
    ]


class VkBufferMemoryBarrier(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("srcAccessMask", c_uint32), ("dstAccessMask", c_uint32),
        ("srcQueueFamilyIndex", c_uint32), ("dstQueueFamilyIndex", c_uint32),
        ("buffer", c_uint64), ("offset", c_uint64), ("size", c_uint64),
    ]


class VkImageSubresourceRange(ctypes.Structure):
    _fields_ = [
        ("aspectMask", c_uint32), ("baseMipLevel", c_uint32), ("levelCount", c_uint32),
        ("baseArrayLayer", c_uint32), ("layerCount", c_uint32),
    ]


class VkImageMemoryBarrier(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("srcAccessMask", c_uint32), ("dstAccessMask", c_uint32),
        ("oldLayout", c_uint32), ("newLayout", c_uint32),
        ("srcQueueFamilyIndex", c_uint32), ("dstQueueFamilyIndex", c_uint32),
        ("image", c_uint64), ("subresourceRange", VkImageSubresourceRange),
    ]


class VkImageSubresourceLayers(ctypes.Structure):
    _fields_ = [
        ("aspectMask", c_uint32), ("mipLevel", c_uint32),
        ("baseArrayLayer", c_uint32), ("layerCount", c_uint32),
    ]


class VkBufferImageCopy(ctypes.Structure):
    _fields_ = [
        ("bufferOffset", c_uint64), ("bufferRowLength", c_uint32),
        ("bufferImageHeight", c_uint32), ("imageSubresource", VkImageSubresourceLayers),
        ("imageOffset", VkOffset3D), ("imageExtent", VkExtent3D),
    ]


class VkFenceCreateInfo(ctypes.Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]


class VkSemaphoreCreateInfo(ctypes.Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]


class GlassUBO(ctypes.Structure):
    _fields_ = [
        ("res", c_float * 4),
        ("themeA", c_float * 4),
        ("themeB", c_float * 4),
        ("themeC", c_float * 4),
        ("bezel", c_float * 4),
        ("panel0", c_float * 4),
        ("panel1", c_float * 4),
    ]


def _api_version(major, minor, patch=0):
    return (major << 22) | (minor << 12) | patch


def _check(result, what):
    if result != SUCCESS:
        raise RuntimeError(f"{what} failed with Vulkan result {result}")
    return result


def _addr(obj):
    return ctypes.cast(byref(obj), c_void_p)


def _load(getter, owner, name, restype, argtypes):
    raw = getter(owner, name.encode())
    if not raw:
        raise RuntimeError(f"Vulkan entry point {name} is missing")
    return CFUNCTYPE(restype, *argtypes)(raw)


class LiquidGlassRenderer:
    """A borderless X11 window whose pixels come from an NVIDIA Vulkan pipeline."""

    bezel_px = 52
    radius_px = 36
    # See-through was 0.66 and the player text disappeared into the wallpaper.
    # Cutting that transparency by about 40% leaves the pane at 0.60.
    clear_opacity = 0.60

    def __init__(self, width=1280, height=820, title="MP Audio Player (Liquid Glass)"):
        self.width = int(width)
        self.height = int(height)
        self.title = title
        self.device_name = ""
        self.vendor_id = 0
        self.device_type = -1
        self.transparent = False
        self.premultiplied = False
        self.format = FORMAT_B8G8R8A8_UNORM
        self.cursor = (0.0, 0.0)
        self.panels = ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))
        self.mouse_down = False
        self.presses = []
        self.should_close = False
        self.shaped = False
        self._shape_size = (0, 0)
        self._frame = 0
        self._start = time.monotonic()
        self._swapchain = 0
        self._images = []
        self._views = []
        self._framebuffers = []
        self._image_available = []
        self._render_finished = []
        self._fences = []
        self._cmd = []
        self._extent = (0, 0)
        self._readback_buffer = 0
        self._readback_memory = 0
        self._readback_ptr = None
        self._readback_bytes = 0
        self._alive = False
        self._step = "start"

    @property
    def summary(self):
        kind = "discrete" if self.device_type == DISCRETE_GPU else "gpu"
        return (
            f"Vulkan device: {self.device_name} "
            f"(vendor 0x{self.vendor_id:04x}, {kind}, NVIDIA)"
        )

    def open(self):
        self._silence_overlays()
        self._step = "x11 threads"
        self._x11 = ctypes.CDLL("libX11.so.6")
        self._x11.XInitThreads.restype = c_int
        self._x11.XInitThreads()
        self._bind_x11()
        self._install_x_error_handler()
        self._bind_xext()
        self._step = "glfw"
        self._glfw = ctypes.CDLL("libglfw.so.3")
        self._bind_glfw()
        self._glfw.glfwInitHint(GLFW_PLATFORM, GLFW_PLATFORM_X11)
        if not self._glfw.glfwInit():
            raise RuntimeError("glfwInit failed")
        if not self._glfw.glfwVulkanSupported():
            raise RuntimeError("GLFW reports Vulkan is unavailable")
        self._step = "window"
        self._window = self._create_window()
        self._bind_input()
        self._step = "instance"
        self._vulkan = ctypes.CDLL("libvulkan.so.1")
        self._bind_loader()
        self._create_instance()
        self._load_instance()
        self._step = "surface"
        surface = c_uint64()
        _check(
            self._glfw.glfwCreateWindowSurface(self._instance, self._window, None, byref(surface)),
            "glfwCreateWindowSurface",
        )
        self._surface = surface.value
        self._step = "device"
        self._pick_nvidia_device()
        self._create_device()
        self._load_device()
        self._step = "swapchain"
        self._create_swapchain()
        self._step = "pipeline"
        self._create_pipeline()
        self._step = "descriptors"
        self._create_descriptors()
        self._step = "commands"
        self._create_commands()
        self._apply_shape()
        self._alive = True
        print(self.summary, flush=True)
        return self

    def close(self):
        if not self._alive:
            self._destroy_window()
            return
        try:
            self._vk.DeviceWaitIdle(self._device)
        except Exception:
            pass
        self._destroy_readback()
        for fence in self._fences:
            self._vk.DestroyFence(self._device, fence, None)
        for sem in self._image_available + self._render_finished:
            self._vk.DestroySemaphore(self._device, sem, None)
        if getattr(self, "_pool", 0):
            self._vk.DestroyCommandPool(self._device, self._pool, None)
        self._destroy_swapchain_views()
        if getattr(self, "_pipeline", 0):
            self._vk.DestroyPipeline(self._device, self._pipeline, None)
        if getattr(self, "_layout", 0):
            self._vk.DestroyPipelineLayout(self._device, self._layout, None)
        if getattr(self, "_render_pass", 0):
            self._vk.DestroyRenderPass(self._device, self._render_pass, None)
        if getattr(self, "_desc_pool", 0):
            self._vk.DestroyDescriptorPool(self._device, self._desc_pool, None)
        if getattr(self, "_desc_layout", 0):
            self._vk.DestroyDescriptorSetLayout(self._device, self._desc_layout, None)
        if getattr(self, "_ubo", 0):
            self._vk.DestroyBuffer(self._device, self._ubo, None)
        if getattr(self, "_ubo_memory", 0):
            self._vk.FreeMemory(self._device, self._ubo_memory, None)
        for mod in getattr(self, "_modules", []):
            self._vk.DestroyShaderModule(self._device, mod, None)
        if self._swapchain:
            self._vk.DestroySwapchainKHR(self._device, self._swapchain, None)
        self._vk.DestroyDevice(self._device, None)
        self._i.DestroySurfaceKHR(self._instance, self._surface, None)
        self._i.DestroyInstance(self._instance, None)
        self._alive = False
        self._destroy_window()

    def request_close(self):
        self.should_close = True
        if getattr(self, "_window", None):
            self._glfw.glfwSetWindowShouldClose(self._window, 1)

    def set_panels(self, panels):
        """Window-pixel rectangles for the darker glass panels. Two at most."""
        rects = []
        for rect in list(panels)[:2]:
            x, y, w, h = rect
            rects.append((float(x), float(y), float(w), float(h)))
        while len(rects) < 2:
            rects.append((0.0, 0.0, 0.0, 0.0))
        self.panels = tuple(rects)

    def window_size(self):
        w, h = c_int(), c_int()
        self._glfw.glfwGetWindowSize(self._window, byref(w), byref(h))
        return int(w.value), int(h.value)

    def framebuffer_size(self):
        w, h = c_int(), c_int()
        self._glfw.glfwGetFramebufferSize(self._window, byref(w), byref(h))
        return max(1, int(w.value)), max(1, int(h.value))

    def window_pos(self):
        x, y = c_int(), c_int()
        self._glfw.glfwGetWindowPos(self._window, byref(x), byref(y))
        return int(x.value), int(y.value)

    def set_window_pos(self, x, y):
        self._glfw.glfwSetWindowPos(self._window, int(x), int(y))

    def set_window_size(self, w, h):
        self._glfw.glfwSetWindowSize(self._window, int(w), int(h))
        self._resize = True

    def x11_window(self):
        return int(self._glfw.glfwGetX11Window(self._window))

    def x11_display(self):
        return self._glfw.glfwGetX11Display(self._window)

    def poll(self):
        self._glfw.glfwPollEvents()
        if self._glfw.glfwWindowShouldClose(self._window):
            self.should_close = True
        return not self.should_close

    def draw(self, theme_name, opacity=1.0, capture=False):
        if not self.poll():
            return None
        fw, fh = self.framebuffer_size()
        if fw < 2 or fh < 2:
            return None
        if getattr(self, "_resize", False) or (fw, fh) != self._extent:
            self._recreate_swapchain()
        if self.window_size() != self._shape_size:
            self._apply_shape()
        colors = theme_rgb(theme_name)
        self._write_ubo(colors, opacity)
        return self._render(capture)

    def _silence_overlays(self):
        os.environ.setdefault("DISABLE_MANGOHUD", "1")
        os.environ.setdefault("DISABLE_VKBASALT", "1")
        os.environ.setdefault(
            "VK_LOADER_LAYERS_DISABLE",
            "VK_LAYER_MANGOHUD_overlay_x86_64,VK_LAYER_MANGOHUD_overlay_x86,"
            "VK_LAYER_VKBASALT_post_processing,VK_LAYER_OBS_vkcapture_64,"
            "VK_LAYER_VALVE_steam_overlay_64,VK_LAYER_VALVE_steam_fossilize_64",
        )

    def _bind_x11(self):
        x = self._x11
        x.XOpenDisplay.restype = c_void_p
        x.XOpenDisplay.argtypes = [c_char_p]
        x.XReparentWindow.argtypes = [c_void_p, c_uint64, c_uint64, c_int, c_int]
        x.XMoveResizeWindow.argtypes = [c_void_p, c_uint64, c_int, c_int, c_uint32, c_uint32]
        x.XMapWindow.argtypes = [c_void_p, c_uint64]
        x.XFlush.argtypes = [c_void_p]
        x.XSync.argtypes = [c_void_p, c_int]
        x.XQueryTree.argtypes = [
            c_void_p, c_uint64, POINTER(c_uint64), POINTER(c_uint64),
            POINTER(POINTER(c_uint64)), POINTER(c_uint32),
        ]
        x.XQueryTree.restype = c_int
        x.XFree.argtypes = [c_void_p]
        x.XCloseDisplay.argtypes = [c_void_p]
        x.XCreatePixmap.argtypes = [c_void_p, c_uint64, c_uint32, c_uint32, c_uint32]
        x.XCreatePixmap.restype = c_uint64
        x.XFreePixmap.argtypes = [c_void_p, c_uint64]
        x.XCreateGC.argtypes = [c_void_p, c_uint64, c_uint64, c_void_p]
        x.XCreateGC.restype = c_void_p
        x.XFreeGC.argtypes = [c_void_p, c_void_p]
        x.XSetForeground.argtypes = [c_void_p, c_void_p, c_uint64]
        x.XFillRectangle.argtypes = [c_void_p, c_uint64, c_void_p, c_int, c_int, c_uint32, c_uint32]
        x.XFillArc.argtypes = [
            c_void_p, c_uint64, c_void_p, c_int, c_int, c_uint32, c_uint32, c_int, c_int,
        ]
        x.XSetInputFocus.argtypes = [c_void_p, c_uint64, c_int, c_uint64]
        x.XSetErrorHandler.argtypes = [c_void_p]
        x.XSetErrorHandler.restype = c_void_p
        x.XSync.restype = c_int
        x.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]
        x.XInternAtom.restype = c_uint64
        x.XChangeProperty.argtypes = [
            c_void_p, c_uint64, c_uint64, c_uint64, c_int, c_int, c_void_p, c_int,
        ]
        x.XChangeProperty.restype = c_int
        x.XRaiseWindow.argtypes = [c_void_p, c_uint64]
        x.XSetTransientForHint.argtypes = [c_void_p, c_uint64, c_uint64]
        x.XSetTransientForHint.restype = c_int
        x.XGetGeometry.argtypes = [
            c_void_p, c_uint64, POINTER(c_uint64), POINTER(c_int), POINTER(c_int),
            POINTER(c_uint32), POINTER(c_uint32), POINTER(c_uint32), POINTER(c_uint32),
        ]
        x.XGetGeometry.restype = c_int
        x.XTranslateCoordinates.argtypes = [
            c_void_p, c_uint64, c_uint64, c_int, c_int,
            POINTER(c_int), POINTER(c_int), POINTER(c_uint64),
        ]
        x.XTranslateCoordinates.restype = c_int
        x.XDefaultRootWindow.argtypes = [c_void_p]
        x.XDefaultRootWindow.restype = c_uint64
        x.XGetInputFocus.argtypes = [c_void_p, POINTER(c_uint64), POINTER(c_int)]

    def _install_x_error_handler(self):
        @ctypes.CFUNCTYPE(c_int, c_void_p, c_void_p)
        def handler(_display, _event):
            return 0

        self._x_error_handler = handler
        self._x11.XSetErrorHandler(ctypes.cast(handler, c_void_p))

    def _bind_xext(self):
        try:
            ext = ctypes.CDLL("libXext.so.6")
        except OSError:
            self._xext = None
            return
        ext.XShapeCombineMask.argtypes = [c_void_p, c_uint64, c_int, c_int, c_int, c_uint64, c_int]
        ext.XShapeQueryExtents.argtypes = [
            c_void_p, c_uint64,
            POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_uint32), POINTER(c_uint32),
            POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_uint32), POINTER(c_uint32),
        ]
        ext.XShapeQueryExtents.restype = c_int
        self._xext = ext

    def _apply_shape(self):
        """Clip the X11 window to the same rounded rectangle the shader draws."""
        self._shape_size = self.window_size()
        self.shaped = False
        self._apply_desktop_glass()
        if not getattr(self, "_xext", None):
            return
        display = self.x11_display()
        window = self.x11_window()
        width, height = self._shape_size
        if not display or not window or width < 8 or height < 8:
            return
        radius = max(8, min(int(self.radius_px), width // 2 - 1, height // 2 - 1))
        x11 = self._x11
        mask = x11.XCreatePixmap(display, window, width, height, 1)
        if not mask:
            return
        gc = x11.XCreateGC(display, mask, 0, None)
        if not gc:
            x11.XFreePixmap(display, mask)
            return
        diameter = radius * 2
        x11.XSetForeground(display, gc, 0)
        x11.XFillRectangle(display, mask, gc, 0, 0, width, height)
        x11.XSetForeground(display, gc, 1)
        x11.XFillRectangle(display, mask, gc, radius, 0, width - diameter, height)
        x11.XFillRectangle(display, mask, gc, 0, radius, width, height - diameter)
        x11.XFillArc(display, mask, gc, 0, 0, diameter, diameter, 90 * 64, 90 * 64)
        x11.XFillArc(display, mask, gc, width - diameter, 0, diameter, diameter, 0, 90 * 64)
        x11.XFillArc(display, mask, gc, 0, height - diameter, diameter, diameter, 180 * 64, 90 * 64)
        x11.XFillArc(display, mask, gc, width - diameter, height - diameter, diameter, diameter, 270 * 64, 90 * 64)
        self._xext.XShapeCombineMask(display, window, 0, 0, 0, mask, 0)
        x11.XFreeGC(display, gc)
        x11.XFreePixmap(display, mask)
        x11.XFlush(display)
        self.shaped = self._window_is_shaped()

    def _window_is_shaped(self):
        if not getattr(self, "_xext", None):
            return False
        bounding = c_int()
        clip = c_int()
        bx = c_int()
        by = c_int()
        cx = c_int()
        cy = c_int()
        bw = c_uint32()
        bh = c_uint32()
        cw = c_uint32()
        ch = c_uint32()
        ok = self._xext.XShapeQueryExtents(
            self.x11_display(), self.x11_window(),
            byref(bounding), byref(bx), byref(by), byref(bw), byref(bh),
            byref(clip), byref(cx), byref(cy), byref(cw), byref(ch),
        )
        return bool(ok and bounding.value)

    def _x_atom(self, name):
        atoms = getattr(self, "_x_atoms", None)
        if atoms is None:
            atoms = {}
            self._x_atoms = atoms
        if name not in atoms:
            atoms[name] = int(self._x11.XInternAtom(self.x11_display(), name.encode("ascii"), 0))
        return atoms[name]

    def _change_cardinal(self, window, prop, values):
        data = (c_uint32 * len(values))(*[int(value) & 0xFFFFFFFF for value in values])
        self._prop_keep = data
        self._x11.XChangeProperty(
            self.x11_display(),
            int(window),
            int(prop),
            self._x_atom("CARDINAL"),
            32,
            0,
            ctypes.cast(data, c_void_p),
            len(values),
        )

    def _set_opacity(self, window, opacity):
        value = int(max(0.0, min(1.0, float(opacity))) * 0xFFFFFFFF)
        self._change_cardinal(window, self._x_atom("_NET_WM_WINDOW_OPACITY"), [value])

    def _apply_desktop_glass(self):
        """Blur the desktop behind the pane and fade it to clear glass.

        Per-pixel Vulkan alpha never reaches the compositor on this GPU.
        """
        window = self.x11_window()
        if not self.x11_display() or not window:
            return
        width, height = self.window_size()
        self._set_opacity(window, self.clear_opacity)
        self._change_cardinal(
            window,
            self._x_atom("_KDE_NET_WM_BLUR_BEHIND_REGION"),
            [0, 0, max(int(width), 1), max(int(height), 1)],
        )
        self._x11.XFlush(self.x11_display())

    def reparent_window(self, child, x, y, width, height):
        display = self.x11_display()
        self._x11.XReparentWindow(display, int(child), self.x11_window(), int(x), int(y))
        self._x11.XMoveResizeWindow(display, int(child), int(x), int(y), int(width), int(height))
        self._x11.XMapWindow(display, int(child))
        # The glass pane is faded. The terminal stays solid so the player can be read.
        self._set_opacity(int(child), 1.0)
        self._x11.XSetInputFocus(display, int(child), 2, 0)
        self._x11.XFlush(display)

    def focus_window(self, window):
        self._x11.XSetInputFocus(self.x11_display(), int(window), 2, 0)
        self._x11.XFlush(self.x11_display())

    def focused_window(self):
        window = c_uint64()
        revert = c_int()
        self._x11.XGetInputFocus(self.x11_display(), byref(window), byref(revert))
        return int(window.value)

    def window_rect(self, window):
        """Screen position and size of an X window."""
        display = self.x11_display()
        root = c_uint64()
        x = c_int()
        y = c_int()
        width = c_uint32()
        height = c_uint32()
        border = c_uint32()
        depth = c_uint32()
        ok = self._x11.XGetGeometry(
            display, int(window), byref(root), byref(x), byref(y),
            byref(width), byref(height), byref(border), byref(depth),
        )
        if not ok:
            return 0, 0, 0, 0
        origin_x = c_int()
        origin_y = c_int()
        child = c_uint64()
        self._x11.XTranslateCoordinates(
            display, int(window), self._x11.XDefaultRootWindow(display),
            0, 0, byref(origin_x), byref(origin_y), byref(child),
        )
        return int(origin_x.value), int(origin_y.value), int(width.value), int(height.value)

    def place_terminal(self, child, x, y, width, height):
        """Keep the player window solid and above the glass pane.

        The toolkit has already moved it to ``x, y``. Moving a managed window
        again with XMoveResizeWindow uses frame-relative coordinates and would
        miss the well.
        """
        del x, y, width, height
        display = self.x11_display()
        child = int(child)
        self._x11.XSetTransientForHint(display, child, self.x11_window())
        self._set_opacity(child, 1.0)
        focused = self.focused_window()
        glass = self.x11_window()
        if focused in (glass, child, self.window_parent(glass), self.window_parent(child)):
            self._x11.XRaiseWindow(display, child)
        self._x11.XFlush(display)

    def window_parent(self, child):
        root = c_uint64()
        parent = c_uint64()
        children = POINTER(c_uint64)()
        count = c_uint32()
        ok = self._x11.XQueryTree(
            self.x11_display(), int(child), byref(root), byref(parent), byref(children), byref(count),
        )
        if children:
            self._x11.XFree(children)
        if not ok:
            return 0
        return int(parent.value)

    def _bind_glfw(self):
        g = self._glfw
        g.glfwInit.restype = c_int
        g.glfwInitHint.argtypes = [c_int, c_int]
        g.glfwWindowHint.argtypes = [c_int, c_int]
        g.glfwVulkanSupported.restype = c_int
        g.glfwCreateWindow.argtypes = [c_int, c_int, c_char_p, c_void_p, c_void_p]
        g.glfwCreateWindow.restype = c_void_p
        g.glfwDestroyWindow.argtypes = [c_void_p]
        g.glfwTerminate.argtypes = []
        g.glfwPollEvents.argtypes = []
        g.glfwWindowShouldClose.argtypes = [c_void_p]
        g.glfwWindowShouldClose.restype = c_int
        g.glfwSetWindowShouldClose.argtypes = [c_void_p, c_int]
        g.glfwSetWindowTitle.argtypes = [c_void_p, c_char_p]
        g.glfwSetWindowPos.argtypes = [c_void_p, c_int, c_int]
        g.glfwSetWindowSize.argtypes = [c_void_p, c_int, c_int]
        g.glfwGetWindowSize.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetWindowPos.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetFramebufferSize.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetCursorPos.argtypes = [c_void_p, POINTER(c_double), POINTER(c_double)]
        g.glfwGetX11Display.argtypes = [c_void_p]
        g.glfwGetX11Display.restype = c_void_p
        g.glfwGetX11Window.argtypes = [c_void_p]
        g.glfwGetX11Window.restype = c_uint64
        g.glfwGetRequiredInstanceExtensions.argtypes = [POINTER(c_uint32)]
        g.glfwGetRequiredInstanceExtensions.restype = POINTER(c_char_p)
        g.glfwCreateWindowSurface.argtypes = [c_void_p, c_void_p, c_void_p, POINTER(c_uint64)]
        g.glfwCreateWindowSurface.restype = c_int
        g.glfwSetMouseButtonCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetMouseButtonCallback.restype = c_void_p
        g.glfwSetCursorPosCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetCursorPosCallback.restype = c_void_p
        g.glfwSetFramebufferSizeCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetFramebufferSizeCallback.restype = c_void_p

    def _bind_loader(self):
        v = self._vulkan
        v.vkGetInstanceProcAddr.restype = c_void_p
        v.vkGetInstanceProcAddr.argtypes = [c_void_p, c_char_p]
        v.vkGetDeviceProcAddr.restype = c_void_p
        v.vkGetDeviceProcAddr.argtypes = [c_void_p, c_char_p]
        v.vkCreateInstance.restype = c_int32
        v.vkCreateInstance.argtypes = [c_void_p, c_void_p, POINTER(c_void_p)]

    def _create_window(self):
        g = self._glfw
        g.glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API)
        g.glfwWindowHint(GLFW_RESIZABLE, GLFW_TRUE)
        g.glfwWindowHint(GLFW_DECORATED, GLFW_FALSE)
        g.glfwWindowHint(GLFW_FOCUS_ON_SHOW, GLFW_TRUE)
        g.glfwWindowHint(GLFW_VISIBLE, GLFW_TRUE)
        g.glfwWindowHint(GLFW_FOCUSED, GLFW_TRUE)
        g.glfwWindowHint(GLFW_TRANSPARENT, GLFW_TRUE)
        title = self.title.encode()
        window = g.glfwCreateWindow(self.width, self.height, title, None, None)
        self.transparent = True
        if not window:
            g.glfwWindowHint(GLFW_TRANSPARENT, GLFW_FALSE)
            window = g.glfwCreateWindow(self.width, self.height, title, None, None)
            self.transparent = False
        if not window:
            raise RuntimeError("GLFW could not open an X11 window for Vulkan")
        g.glfwSetWindowPos(window, 72, 64)
        self._resize = False
        return window

    def _bind_input(self):
        self._on_mouse = CFUNCTYPE(None, c_void_p, c_int, c_int, c_int)(self._mouse_button)
        self._on_cursor = CFUNCTYPE(None, c_void_p, c_double, c_double)(self._cursor)
        self._on_fb = CFUNCTYPE(None, c_void_p, c_int, c_int)(self._framebuffer)
        self._glfw.glfwSetMouseButtonCallback(self._window, ctypes.cast(self._on_mouse, c_void_p))
        self._glfw.glfwSetCursorPosCallback(self._window, ctypes.cast(self._on_cursor, c_void_p))
        self._glfw.glfwSetFramebufferSizeCallback(self._window, ctypes.cast(self._on_fb, c_void_p))

    def _mouse_button(self, _window, button, action, _mods):
        if button == 0:
            self.mouse_down = action == GLFW_PRESS
            if action == GLFW_PRESS:
                self.presses.append(self.cursor)

    def _cursor(self, _window, x, y):
        self.cursor = (float(x), float(y))

    def _framebuffer(self, _window, _w, _h):
        self._resize = True

    def _create_instance(self):
        count = c_uint32()
        ptr = self._glfw.glfwGetRequiredInstanceExtensions(byref(count))
        names = []
        for i in range(count.value):
            names.append(ptr[i])
        self._ext_names = names
        arr = (c_char_p * len(names))(*names)
        self._ext_arr = arr
        app = VkApplicationInfo()
        app.sType = ST_APPLICATION_INFO
        app.pApplicationName = b"MP Audio Player Liquid Glass"
        app.applicationVersion = _api_version(0, 4, 0)
        app.pEngineName = b"mp-liquid-glass"
        app.engineVersion = 1
        app.apiVersion = _api_version(1, 2, 0)
        self._app = app
        info = VkInstanceCreateInfo()
        info.sType = ST_INSTANCE_CREATE_INFO
        info.pApplicationInfo = _addr(app)
        info.enabledExtensionCount = len(names)
        info.ppEnabledExtensionNames = ctypes.cast(arr, c_void_p)
        self._instance_info = info
        instance = c_void_p()
        _check(self._vulkan.vkCreateInstance(_addr(info), None, byref(instance)), "vkCreateInstance")
        self._instance = instance

    def _load_instance(self):
        g = self._vulkan.vkGetInstanceProcAddr
        inst = self._instance

        def load(name, restype, argtypes):
            return _load(g, inst, name, restype, argtypes)

        U32 = c_uint32
        self._i = type("I", (), {})()
        self._i.DestroyInstance = load("vkDestroyInstance", None, [c_void_p, c_void_p])
        self._i.DestroySurfaceKHR = load("vkDestroySurfaceKHR", None, [c_void_p, c_uint64, c_void_p])
        self._i.EnumeratePhysicalDevices = load(
            "vkEnumeratePhysicalDevices", c_int32, [c_void_p, POINTER(U32), POINTER(c_void_p)]
        )
        self._i.GetPhysicalDeviceProperties = load(
            "vkGetPhysicalDeviceProperties", None, [c_void_p, c_void_p]
        )
        self._i.GetPhysicalDeviceQueueFamilyProperties = load(
            "vkGetPhysicalDeviceQueueFamilyProperties", None,
            [c_void_p, POINTER(U32), c_void_p],
        )
        self._i.GetPhysicalDeviceMemoryProperties = load(
            "vkGetPhysicalDeviceMemoryProperties", None, [c_void_p, c_void_p]
        )
        self._i.GetSurfaceSupport = load(
            "vkGetPhysicalDeviceSurfaceSupportKHR", c_int32,
            [c_void_p, U32, c_uint64, POINTER(U32)],
        )
        self._i.GetSurfaceCaps = load(
            "vkGetPhysicalDeviceSurfaceCapabilitiesKHR", c_int32,
            [c_void_p, c_uint64, c_void_p],
        )
        self._i.GetSurfaceFormats = load(
            "vkGetPhysicalDeviceSurfaceFormatsKHR", c_int32,
            [c_void_p, c_uint64, POINTER(U32), c_void_p],
        )
        self._i.GetSurfaceModes = load(
            "vkGetPhysicalDeviceSurfacePresentModesKHR", c_int32,
            [c_void_p, c_uint64, POINTER(U32), c_void_p],
        )
        self._i.CreateDevice = load(
            "vkCreateDevice", c_int32, [c_void_p, c_void_p, c_void_p, POINTER(c_void_p)]
        )

    def _device_header(self, phys):
        # The driver writes a full VkPhysicalDeviceProperties. The buffer is
        # larger than the struct so the write stays inside it.
        buf = (c_uint8 * 16384)()
        self._i.GetPhysicalDeviceProperties(phys, buf)
        api, driver, vendor, device, dtype = ctypes.cast(buf, POINTER(c_uint32 * 5)).contents
        name = ctypes.string_at(ctypes.addressof(buf) + 20, 256).split(b"\0", 1)[0].decode("utf-8", "replace")
        return {
            "api": int(api),
            "driver": int(driver),
            "vendor_id": int(vendor),
            "device_id": int(device),
            "device_type": int(dtype),
            "name": name,
        }

    def _pick_nvidia_device(self):
        count = c_uint32()
        _check(self._i.EnumeratePhysicalDevices(self._instance, byref(count), None), "enumerate devices")
        if count.value == 0:
            raise RuntimeError("Vulkan reported no physical devices")
        raw = (c_void_p * count.value)()
        _check(self._i.EnumeratePhysicalDevices(self._instance, byref(count), raw), "enumerate devices")
        devices = []
        headers = []
        for i in range(count.value):
            header = self._device_header(raw[i])
            headers.append(header)
            devices.append(header)
        index = select_nvidia_device(devices)
        self._physical = raw[index]
        chosen = headers[index]
        self.device_name = chosen["name"]
        self.vendor_id = chosen["vendor_id"]
        self.device_type = chosen["device_type"]
        if self.vendor_id != NVIDIA_VENDOR_ID:
            raise RuntimeError(f"Refusing to render on {self.device_name}")
        self._queue_family = self._present_family(self._physical)

    def _present_family(self, phys):
        count = c_uint32()
        self._i.GetPhysicalDeviceQueueFamilyProperties(phys, byref(count), None)
        props = (VkQueueFamilyProperties * count.value)()
        self._i.GetPhysicalDeviceQueueFamilyProperties(phys, byref(count), props)
        for i in range(count.value):
            if not (props[i].queueFlags & QUEUE_GRAPHICS):
                continue
            support = c_uint32()
            _check(self._i.GetSurfaceSupport(phys, i, self._surface, byref(support)), "surface support")
            if support.value:
                return i
        raise RuntimeError(f"{self.device_name} has no Vulkan graphics queue that can present this window")

    def _create_device(self):
        priority = (c_float * 1)(1.0)
        self._priority = priority
        q = VkDeviceQueueCreateInfo()
        q.sType = ST_DEVICE_QUEUE_CREATE_INFO
        q.queueFamilyIndex = self._queue_family
        q.queueCount = 1
        q.pQueuePriorities = ctypes.cast(priority, c_void_p)
        self._queue_info = q
        ext = (c_char_p * 1)(b"VK_KHR_swapchain")
        self._dev_ext = ext
        info = VkDeviceCreateInfo()
        info.sType = ST_DEVICE_CREATE_INFO
        info.queueCreateInfoCount = 1
        info.pQueueCreateInfos = _addr(q)
        info.enabledExtensionCount = 1
        info.ppEnabledExtensionNames = ctypes.cast(ext, c_void_p)
        self._device_info = info
        device = c_void_p()
        _check(self._i.CreateDevice(self._physical, _addr(info), None, byref(device)), "vkCreateDevice")
        self._device = device

    def _load_device(self):
        g = self._vulkan.vkGetDeviceProcAddr
        dev = self._device

        def load(name, restype, argtypes):
            return _load(g, dev, name, restype, argtypes)

        U32 = c_uint32
        P = c_void_p
        H = c_uint64
        self._vk = type("D", (), {})()
        vk = self._vk
        vk.GetDeviceQueue = load("vkGetDeviceQueue", None, [P, U32, U32, POINTER(P)])
        vk.DeviceWaitIdle = load("vkDeviceWaitIdle", c_int32, [P])
        vk.DestroyDevice = load("vkDestroyDevice", None, [P, P])
        vk.CreateSwapchainKHR = load("vkCreateSwapchainKHR", c_int32, [P, P, P, POINTER(H)])
        vk.DestroySwapchainKHR = load("vkDestroySwapchainKHR", None, [P, H, P])
        vk.GetSwapchainImagesKHR = load("vkGetSwapchainImagesKHR", c_int32, [P, H, POINTER(U32), POINTER(H)])
        vk.CreateImageView = load("vkCreateImageView", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyImageView = load("vkDestroyImageView", None, [P, H, P])
        vk.CreateRenderPass = load("vkCreateRenderPass", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyRenderPass = load("vkDestroyRenderPass", None, [P, H, P])
        vk.CreateFramebuffer = load("vkCreateFramebuffer", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyFramebuffer = load("vkDestroyFramebuffer", None, [P, H, P])
        vk.CreateShaderModule = load("vkCreateShaderModule", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyShaderModule = load("vkDestroyShaderModule", None, [P, H, P])
        vk.CreatePipelineLayout = load("vkCreatePipelineLayout", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyPipelineLayout = load("vkDestroyPipelineLayout", None, [P, H, P])
        vk.CreateGraphicsPipelines = load("vkCreateGraphicsPipelines", c_int32, [P, H, U32, P, P, POINTER(H)])
        vk.DestroyPipeline = load("vkDestroyPipeline", None, [P, H, P])
        vk.CreateDescriptorSetLayout = load("vkCreateDescriptorSetLayout", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyDescriptorSetLayout = load("vkDestroyDescriptorSetLayout", None, [P, H, P])
        vk.CreateDescriptorPool = load("vkCreateDescriptorPool", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyDescriptorPool = load("vkDestroyDescriptorPool", None, [P, H, P])
        vk.AllocateDescriptorSets = load("vkAllocateDescriptorSets", c_int32, [P, P, POINTER(H)])
        vk.UpdateDescriptorSets = load("vkUpdateDescriptorSets", None, [P, U32, P, U32, P])
        vk.CreateBuffer = load("vkCreateBuffer", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyBuffer = load("vkDestroyBuffer", None, [P, H, P])
        vk.GetBufferMemoryRequirements = load("vkGetBufferMemoryRequirements", None, [P, H, P])
        vk.AllocateMemory = load("vkAllocateMemory", c_int32, [P, P, P, POINTER(H)])
        vk.FreeMemory = load("vkFreeMemory", None, [P, H, P])
        vk.BindBufferMemory = load("vkBindBufferMemory", c_int32, [P, H, H, c_uint64])
        vk.MapMemory = load("vkMapMemory", c_int32, [P, H, c_uint64, c_uint64, U32, POINTER(P)])
        vk.UnmapMemory = load("vkUnmapMemory", None, [P, H])
        vk.CreateCommandPool = load("vkCreateCommandPool", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyCommandPool = load("vkDestroyCommandPool", None, [P, H, P])
        vk.AllocateCommandBuffers = load("vkAllocateCommandBuffers", c_int32, [P, P, POINTER(P)])
        vk.BeginCommandBuffer = load("vkBeginCommandBuffer", c_int32, [P, P])
        vk.EndCommandBuffer = load("vkEndCommandBuffer", c_int32, [P])
        vk.ResetCommandBuffer = load("vkResetCommandBuffer", c_int32, [P, U32])
        vk.CmdBeginRenderPass = load("vkCmdBeginRenderPass", None, [P, P, U32])
        vk.CmdEndRenderPass = load("vkCmdEndRenderPass", None, [P])
        vk.CmdBindPipeline = load("vkCmdBindPipeline", None, [P, U32, H])
        vk.CmdBindDescriptorSets = load("vkCmdBindDescriptorSets", None, [P, U32, H, U32, U32, P, U32, P])
        vk.CmdDraw = load("vkCmdDraw", None, [P, U32, U32, U32, U32])
        vk.CmdBindVertexBuffers = load("vkCmdBindVertexBuffers", None, [P, U32, U32, P, P])
        vk.CmdSetViewport = load("vkCmdSetViewport", None, [P, U32, U32, P])
        vk.CmdSetScissor = load("vkCmdSetScissor", None, [P, U32, U32, P])
        vk.CmdPipelineBarrier = load(
            "vkCmdPipelineBarrier", None,
            [P, U32, U32, U32, U32, P, U32, P, U32, P],
        )
        vk.CmdCopyImageToBuffer = load("vkCmdCopyImageToBuffer", None, [P, H, U32, H, U32, P])
        vk.CreateSemaphore = load("vkCreateSemaphore", c_int32, [P, P, P, POINTER(H)])
        vk.DestroySemaphore = load("vkDestroySemaphore", None, [P, H, P])
        vk.CreateFence = load("vkCreateFence", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyFence = load("vkDestroyFence", None, [P, H, P])
        vk.WaitForFences = load("vkWaitForFences", c_int32, [P, U32, P, U32, c_uint64])
        vk.ResetFences = load("vkResetFences", c_int32, [P, U32, P])
        vk.AcquireNextImageKHR = load(
            "vkAcquireNextImageKHR", c_int32, [P, H, c_uint64, H, H, POINTER(U32)]
        )
        vk.QueueSubmit = load("vkQueueSubmit", c_int32, [P, U32, P, H])
        vk.QueuePresentKHR = load("vkQueuePresentKHR", c_int32, [P, P])
        vk.QueueWaitIdle = load("vkQueueWaitIdle", c_int32, [P])
        queue = c_void_p()
        vk.GetDeviceQueue(self._device, self._queue_family, 0, byref(queue))
        self._queue = queue

    def _surface_choices(self):
        caps = VkSurfaceCapabilitiesKHR()
        _check(self._i.GetSurfaceCaps(self._physical, self._surface, _addr(caps)), "surface caps")
        count = c_uint32()
        _check(self._i.GetSurfaceFormats(self._physical, self._surface, byref(count), None), "surface formats")
        formats = (VkSurfaceFormatKHR * count.value)()
        _check(self._i.GetSurfaceFormats(self._physical, self._surface, byref(count), formats), "surface formats")
        preferred = (FORMAT_B8G8R8A8_UNORM, FORMAT_R8G8B8A8_UNORM, FORMAT_B8G8R8A8_SRGB)
        chosen = formats[0]
        for want in preferred:
            for fmt in formats:
                if fmt.format == want:
                    chosen = fmt
                    break
            else:
                continue
            break
        modes_n = c_uint32()
        _check(self._i.GetSurfaceModes(self._physical, self._surface, byref(modes_n), None), "present modes")
        modes = (c_uint32 * modes_n.value)()
        _check(self._i.GetSurfaceModes(self._physical, self._surface, byref(modes_n), modes), "present modes")
        present = PRESENT_FIFO if any(modes[i] == PRESENT_FIFO for i in range(modes_n.value)) else modes[0]
        return caps, chosen, present

    def _choose_composite(self, caps):
        supported = caps.supportedCompositeAlpha
        if self.transparent and supported & COMPOSITE_PRE:
            self.premultiplied = True
            return COMPOSITE_PRE
        if self.transparent and supported & COMPOSITE_INHERIT:
            self.premultiplied = True
            return COMPOSITE_INHERIT
        if self.transparent and supported & COMPOSITE_POST:
            self.premultiplied = False
            return COMPOSITE_POST
        self.premultiplied = False
        self.transparent = False
        return COMPOSITE_OPAQUE

    def _create_swapchain(self, old=0):
        caps, fmt, present = self._surface_choices()
        self.format = int(fmt.format)
        self._colorspace = int(fmt.colorSpace)
        composite = self._choose_composite(caps)
        fw, fh = self.framebuffer_size()
        if caps.currentExtent.width != 0xFFFFFFFF:
            extent = (int(caps.currentExtent.width), int(caps.currentExtent.height))
        else:
            extent = (
                min(max(fw, caps.minImageExtent.width), caps.maxImageExtent.width),
                min(max(fh, caps.minImageExtent.height), caps.maxImageExtent.height),
            )
        if extent[0] == 0 or extent[1] == 0:
            extent = (fw, fh)
        image_count = max(caps.minImageCount, 3)
        if caps.maxImageCount:
            image_count = min(image_count, caps.maxImageCount)
        usage = IMAGE_USAGE_COLOR
        if caps.supportedUsageFlags & IMAGE_USAGE_TRANSFER_SRC:
            usage |= IMAGE_USAGE_TRANSFER_SRC
            self._can_readback = True
        else:
            self._can_readback = False
        info = VkSwapchainCreateInfoKHR()
        info.sType = ST_SWAPCHAIN_CREATE
        info.surface = self._surface
        info.minImageCount = image_count
        info.imageFormat = self.format
        info.imageColorSpace = self._colorspace
        info.imageExtent = VkExtent2D(extent[0], extent[1])
        info.imageArrayLayers = 1
        info.imageUsage = usage
        info.imageSharingMode = SHARING_EXCLUSIVE
        info.preTransform = caps.currentTransform or TRANSFORM_IDENTITY
        info.compositeAlpha = composite
        info.presentMode = present
        info.clipped = 1
        info.oldSwapchain = old
        self._swap_info = info
        swap = c_uint64()
        _check(self._vk.CreateSwapchainKHR(self._device, _addr(info), None, byref(swap)), "vkCreateSwapchainKHR")
        if old:
            self._vk.DestroySwapchainKHR(self._device, old, None)
        self._swapchain = swap.value
        self._extent = extent
        count = c_uint32()
        _check(self._vk.GetSwapchainImagesKHR(self._device, self._swapchain, byref(count), None), "swapchain images")
        images = (c_uint64 * count.value)()
        _check(self._vk.GetSwapchainImagesKHR(self._device, self._swapchain, byref(count), images), "swapchain images")
        self._images = [int(images[i]) for i in range(count.value)]
        self._views = []
        self._framebuffers = []
        for image in self._images:
            view_info = VkImageViewCreateInfo()
            view_info.sType = ST_IMAGE_VIEW_CREATE_INFO
            view_info.image = image
            view_info.viewType = IMAGE_VIEW_2D
            view_info.format = self.format
            view_info.r = view_info.g = view_info.b = view_info.a = 0
            view_info.aspectMask = IMAGE_ASPECT_COLOR
            view_info.levelCount = 1
            view_info.layerCount = 1
            view = c_uint64()
            _check(self._vk.CreateImageView(self._device, _addr(view_info), None, byref(view)), "image view")
            self._views.append(view.value)
        if not getattr(self, "_render_pass", 0):
            self._create_render_pass()
        self._create_framebuffers()

    def _create_render_pass(self):
        attachment = VkAttachmentDescription()
        attachment.format = self.format
        attachment.samples = SAMPLE_1
        attachment.loadOp = LOAD_CLEAR
        attachment.storeOp = STORE_STORE
        attachment.stencilLoadOp = LOAD_DONT
        attachment.stencilStoreOp = STORE_DONT
        attachment.initialLayout = LAYOUT_UNDEFINED
        attachment.finalLayout = LAYOUT_PRESENT
        ref = VkAttachmentReference(0, LAYOUT_COLOR)
        sub = VkSubpassDescription()
        sub.pipelineBindPoint = 0
        sub.colorAttachmentCount = 1
        sub.pColorAttachments = _addr(ref)
        deps = (VkSubpassDependency * 2)()
        deps[0].srcSubpass = SUBPASS_EXTERNAL
        deps[0].dstSubpass = 0
        deps[0].srcStageMask = STAGE_COLOR_OUT
        deps[0].dstStageMask = STAGE_COLOR_OUT
        deps[0].dstAccessMask = ACCESS_COLOR_WRITE
        deps[1].srcSubpass = 0
        deps[1].dstSubpass = SUBPASS_EXTERNAL
        deps[1].srcStageMask = STAGE_COLOR_OUT
        deps[1].dstStageMask = STAGE_BOTTOM
        deps[1].srcAccessMask = ACCESS_COLOR_WRITE
        info = VkRenderPassCreateInfo()
        info.sType = ST_RENDER_PASS
        info.attachmentCount = 1
        info.pAttachments = _addr(attachment)
        info.subpassCount = 1
        info.pSubpasses = _addr(sub)
        info.dependencyCount = 2
        info.pDependencies = ctypes.cast(deps, c_void_p)
        self._rp_keep = (attachment, ref, sub, deps, info)
        rp = c_uint64()
        _check(self._vk.CreateRenderPass(self._device, _addr(info), None, byref(rp)), "render pass")
        self._render_pass = rp.value

    def _create_framebuffers(self):
        self._fb_keeps = []
        for view in self._views:
            views = (c_uint64 * 1)(view)
            info = VkFramebufferCreateInfo()
            info.sType = ST_FRAMEBUFFER
            info.renderPass = self._render_pass
            info.attachmentCount = 1
            info.pAttachments = ctypes.cast(views, c_void_p)
            info.width, info.height = self._extent
            info.layers = 1
            fb = c_uint64()
            self._fb_keeps.append((views, info))
            _check(self._vk.CreateFramebuffer(self._device, _addr(info), None, byref(fb)), "framebuffer")
            self._framebuffers.append(fb.value)

    def _destroy_swapchain_views(self):
        for fb in self._framebuffers:
            self._vk.DestroyFramebuffer(self._device, fb, None)
        for view in self._views:
            self._vk.DestroyImageView(self._device, view, None)
        self._framebuffers = []
        self._views = []

    def _recreate_swapchain(self):
        self._vk.DeviceWaitIdle(self._device)
        self._destroy_swapchain_views()
        old = self._swapchain
        self._create_swapchain(old)
        self._resize = False
        self._destroy_readback()

    def _shader_module(self, path):
        data = Path(path).read_bytes()
        if len(data) % 4:
            raise RuntimeError(f"{path} is not aligned SPIR-V")
        buf = (c_uint8 * len(data)).from_buffer_copy(data)
        info = VkShaderModuleCreateInfo()
        info.sType = ST_SHADER_MODULE_CREATE_INFO
        info.codeSize = len(data)
        info.pCode = ctypes.cast(buf, c_void_p)
        mod = c_uint64()
        self._shader_keep = getattr(self, "_shader_keep", [])
        self._shader_keep.append((buf, info))
        _check(self._vk.CreateShaderModule(self._device, _addr(info), None, byref(mod)), f"shader {path.name}")
        return mod.value

    def _create_pipeline(self):
        vert = self._shader_module(SHADER_DIR / "liquid_glass.vert.spv")
        frag = self._shader_module(SHADER_DIR / "liquid_glass.frag.spv")
        self._modules = [vert, frag]
        stages = (VkPipelineShaderStageCreateInfo * 2)()
        for stage, mod, bit in ((0, vert, SHADER_VERTEX), (1, frag, SHADER_FRAGMENT)):
            stages[stage].sType = ST_PIPELINE_SHADER_STAGE
            stages[stage].stage = bit
            stages[stage].module = mod
            stages[stage].pName = b"main"
        vertex = VkPipelineVertexInputStateCreateInfo()
        vertex.sType = ST_PIPELINE_VERTEX_INPUT
        assembly = VkPipelineInputAssemblyStateCreateInfo()
        assembly.sType = ST_PIPELINE_INPUT_ASSEMBLY
        assembly.topology = TOPOLOGY_TRIANGLE_LIST
        vp = VkViewport(0, 0, float(self._extent[0]), float(self._extent[1]), 0.0, 1.0)
        sc = VkRect2D(VkOffset2D(0, 0), VkExtent2D(self._extent[0], self._extent[1]))
        viewport = VkPipelineViewportStateCreateInfo()
        viewport.sType = ST_PIPELINE_VIEWPORT
        viewport.viewportCount = 1
        viewport.pViewports = _addr(vp)
        viewport.scissorCount = 1
        viewport.pScissors = _addr(sc)
        raster = VkPipelineRasterizationStateCreateInfo()
        raster.sType = ST_PIPELINE_RASTER
        raster.polygonMode = 0
        raster.lineWidth = 1.0
        multi = VkPipelineMultisampleStateCreateInfo()
        multi.sType = ST_PIPELINE_MULTISAMPLE
        multi.rasterizationSamples = SAMPLE_1
        blend_att = VkPipelineColorBlendAttachmentState()
        blend_att.colorWriteMask = COLOR_WRITE_ALL
        if self.premultiplied:
            blend_att.blendEnable = 1
            blend_att.srcColorBlendFactor = BLEND_ONE
            blend_att.dstColorBlendFactor = BLEND_ONE_MINUS_SRC_ALPHA
            blend_att.colorBlendOp = BLEND_ADD
            blend_att.srcAlphaBlendFactor = BLEND_ONE
            blend_att.dstAlphaBlendFactor = BLEND_ONE_MINUS_SRC_ALPHA
            blend_att.alphaBlendOp = BLEND_ADD
        blend = VkPipelineColorBlendStateCreateInfo()
        blend.sType = ST_PIPELINE_COLOR_BLEND
        blend.attachmentCount = 1
        blend.pAttachments = _addr(blend_att)
        dynamics = (c_uint32 * 2)(DYNAMIC_VIEWPORT, DYNAMIC_SCISSOR)
        dynamic = VkPipelineDynamicStateCreateInfo()
        dynamic.sType = ST_PIPELINE_DYNAMIC
        dynamic.dynamicStateCount = 2
        dynamic.pDynamicStates = ctypes.cast(dynamics, c_void_p)
        binding = VkDescriptorSetLayoutBinding()
        binding.binding = 0
        binding.descriptorType = DESCRIPTOR_UNIFORM
        binding.descriptorCount = 1
        binding.stageFlags = STAGE_VERTEX_BIT | STAGE_FRAGMENT_BIT
        set_info = VkDescriptorSetLayoutCreateInfo()
        set_info.sType = ST_DESCRIPTOR_SET_LAYOUT
        set_info.bindingCount = 1
        set_info.pBindings = _addr(binding)
        desc_layout = c_uint64()
        _check(
            self._vk.CreateDescriptorSetLayout(self._device, _addr(set_info), None, byref(desc_layout)),
            "descriptor layout",
        )
        self._desc_layout = desc_layout.value
        layouts = (c_uint64 * 1)(self._desc_layout)
        pipe_layout_info = VkPipelineLayoutCreateInfo()
        pipe_layout_info.sType = ST_PIPELINE_LAYOUT
        pipe_layout_info.setLayoutCount = 1
        pipe_layout_info.pSetLayouts = ctypes.cast(layouts, c_void_p)
        self._layout_sets = 1
        layout = c_uint64()
        _check(
            self._vk.CreatePipelineLayout(self._device, _addr(pipe_layout_info), None, byref(layout)),
            "pipeline layout",
        )
        self._layout = layout.value
        gp = VkGraphicsPipelineCreateInfo()
        gp.sType = ST_GRAPHICS_PIPELINE
        gp.stageCount = 2
        gp.pStages = ctypes.cast(stages, c_void_p)
        gp.pVertexInputState = _addr(vertex)
        gp.pInputAssemblyState = _addr(assembly)
        gp.pViewportState = _addr(viewport)
        gp.pRasterizationState = _addr(raster)
        gp.pMultisampleState = _addr(multi)
        gp.pColorBlendState = _addr(blend)
        gp.pDynamicState = _addr(dynamic)
        gp.layout = self._layout
        gp.renderPass = self._render_pass
        gp.basePipelineIndex = -1
        self._pipe_keep = (
            stages, vertex, assembly, vp, sc, viewport, raster, multi,
            blend_att, blend, dynamics, dynamic, binding, set_info, layouts,
            pipe_layout_info, gp,
        )
        pipeline = c_uint64()
        _check(
            self._vk.CreateGraphicsPipelines(self._device, 0, 1, _addr(gp), None, byref(pipeline)),
            "graphics pipeline",
        )
        self._pipeline = pipeline.value

    def _memory_type(self, bits, flags):
        props = VkPhysicalDeviceMemoryProperties()
        self._i.GetPhysicalDeviceMemoryProperties(self._physical, _addr(props))
        for i in range(props.memoryTypeCount):
            if bits & (1 << i) and (props.memoryTypes[i].propertyFlags & flags) == flags:
                return i
        raise RuntimeError("No host-visible Vulkan memory type on the NVIDIA device")

    def _create_buffer(self, size, usage):
        info = VkBufferCreateInfo()
        info.sType = ST_BUFFER_CREATE_INFO
        info.size = size
        info.usage = usage
        info.sharingMode = SHARING_EXCLUSIVE
        buf = c_uint64()
        _check(self._vk.CreateBuffer(self._device, _addr(info), None, byref(buf)), "buffer")
        req = VkMemoryRequirements()
        self._vk.GetBufferMemoryRequirements(self._device, buf.value, _addr(req))
        alloc = VkMemoryAllocateInfo()
        alloc.sType = ST_MEMORY_ALLOCATE_INFO
        alloc.allocationSize = req.size
        alloc.memoryTypeIndex = self._memory_type(req.memoryTypeBits, MEMORY_HOST_VISIBLE | MEMORY_HOST_COHERENT)
        mem = c_uint64()
        _check(self._vk.AllocateMemory(self._device, _addr(alloc), None, byref(mem)), "memory")
        _check(self._vk.BindBufferMemory(self._device, buf.value, mem.value, 0), "bind memory")
        return buf.value, mem.value, int(req.size)

    def _create_descriptors(self):
        self._ubo, self._ubo_memory, _ = self._create_buffer(256, 0x10)  # UNIFORM_BUFFER
        ptr = c_void_p()
        _check(self._vk.MapMemory(self._device, self._ubo_memory, 0, 256, 0, byref(ptr)), "map ubo")
        self._ubo_ptr = ptr
        pool_size = VkDescriptorPoolSize(DESCRIPTOR_UNIFORM, 1)
        pool_info = VkDescriptorPoolCreateInfo()
        pool_info.sType = ST_DESCRIPTOR_POOL
        pool_info.maxSets = 1
        pool_info.poolSizeCount = 1
        pool_info.pPoolSizes = _addr(pool_size)
        pool = c_uint64()
        _check(self._vk.CreateDescriptorPool(self._device, _addr(pool_info), None, byref(pool)), "descriptor pool")
        self._desc_pool = pool.value
        layouts = (c_uint64 * 1)(self._desc_layout)
        alloc_info = VkDescriptorSetAllocateInfo()
        alloc_info.sType = ST_DESCRIPTOR_SET_ALLOCATE
        alloc_info.descriptorPool = self._desc_pool
        alloc_info.descriptorSetCount = 1
        alloc_info.pSetLayouts = ctypes.cast(layouts, c_void_p)
        dset = c_uint64()
        self._desc_keep = (pool_size, pool_info, layouts, alloc_info)
        _check(self._vk.AllocateDescriptorSets(self._device, _addr(alloc_info), byref(dset)), "descriptor set")
        self._dset = dset.value
        buffer_info = VkDescriptorBufferInfo(self._ubo, 0, 256)
        write = VkWriteDescriptorSet()
        write.sType = ST_WRITE_DESCRIPTOR_SET
        write.dstSet = self._dset
        write.descriptorCount = 1
        write.descriptorType = DESCRIPTOR_UNIFORM
        write.pBufferInfo = _addr(buffer_info)
        self._write_keep = (buffer_info, write)
        self._vk.UpdateDescriptorSets(self._device, 1, _addr(write), 0, None)

    def _create_commands(self):
        pool_info = VkCommandPoolCreateInfo()
        pool_info.sType = ST_COMMAND_POOL
        pool_info.flags = CMD_POOL_RESET
        pool_info.queueFamilyIndex = self._queue_family
        pool = c_uint64()
        _check(self._vk.CreateCommandPool(self._device, _addr(pool_info), None, byref(pool)), "command pool")
        self._pool = pool.value
        frames = 2
        alloc = VkCommandBufferAllocateInfo()
        alloc.sType = ST_COMMAND_BUFFER_ALLOCATE
        alloc.commandPool = self._pool
        alloc.level = 0
        alloc.commandBufferCount = frames
        cmds = (c_void_p * frames)()
        self._cmd_alloc = alloc
        _check(self._vk.AllocateCommandBuffers(self._device, _addr(alloc), cmds), "command buffers")
        self._cmd = [cmds[i] for i in range(frames)]
        self._cmd_keep = cmds
        sem_info = VkSemaphoreCreateInfo()
        sem_info.sType = ST_SEMAPHORE_CREATE_INFO
        fence_info = VkFenceCreateInfo()
        fence_info.sType = ST_FENCE_CREATE_INFO
        fence_info.flags = FENCE_SIGNALED
        self._sync_info = (sem_info, fence_info)
        for _ in range(frames):
            sem = c_uint64()
            _check(self._vk.CreateSemaphore(self._device, _addr(sem_info), None, byref(sem)), "semaphore")
            self._image_available.append(sem.value)
            sem2 = c_uint64()
            _check(self._vk.CreateSemaphore(self._device, _addr(sem_info), None, byref(sem2)), "semaphore")
            self._render_finished.append(sem2.value)
            fence = c_uint64()
            _check(self._vk.CreateFence(self._device, _addr(fence_info), None, byref(fence)), "fence")
            self._fences.append(fence.value)
        self._frame = 0

    def _write_ubo(self, colors, opacity):
        ww, wh = self.window_size()
        fw, fh = self._extent
        scale = fw / max(ww, 1)
        margin = self.bezel_px * scale
        radius = self.radius_px * scale
        mx, my = self.cursor
        ubo = GlassUBO()
        ubo.res[:] = (float(fw), float(fh), float(time.monotonic() - self._start), fw / max(fh, 1))
        a, b, c = (_rgb01(colors[0]), _rgb01(colors[1]), _rgb01(colors[2]))
        ubo.themeA[:] = (a[0], a[1], a[2], max(0.0, min(1.0, mx / max(ww, 1))))
        ubo.themeB[:] = (b[0], b[1], b[2], max(0.0, min(1.0, my / max(wh, 1))))
        ubo.themeC[:] = (c[0], c[1], c[2], float(opacity))
        ubo.bezel[:] = (float(margin), float(radius), 1.0 if self.premultiplied else 0.0, 1.0)
        for slot, rect in zip((ubo.panel0, ubo.panel1), self.panels):
            x, y, w, h = rect
            slot[:] = (x * scale, y * scale, w * scale, h * scale)
        ctypes.memmove(self._ubo_ptr, byref(ubo), ctypes.sizeof(ubo))

    def _render(self, capture):
        vk = self._vk
        frame = self._frame
        fence = self._fences[frame]
        _check(vk.WaitForFences(self._device, 1, byref(c_uint64(fence)), 1, 2_000_000_000), "wait fence")
        index = c_uint32()
        acquired = vk.AcquireNextImageKHR(
            self._device, self._swapchain, 2_000_000_000,
            self._image_available[frame], 0, byref(index),
        )
        if acquired in (OUT_OF_DATE, SUBOPTIMAL):
            self._resize = True
            return None
        _check(acquired, "acquire")
        _check(vk.ResetFences(self._device, 1, byref(c_uint64(fence))), "reset fence")
        cmd = self._cmd[frame]
        _check(vk.ResetCommandBuffer(cmd, 0), "reset command")
        begin = VkCommandBufferBeginInfo()
        begin.sType = ST_COMMAND_BUFFER_BEGIN
        begin.flags = CMD_ONE_TIME
        _check(vk.BeginCommandBuffer(cmd, _addr(begin)), "begin command")
        barrier = VkBufferMemoryBarrier()
        barrier.sType = ST_BUFFER_MEMORY_BARRIER
        barrier.srcAccessMask = ACCESS_HOST_WRITE
        barrier.dstAccessMask = ACCESS_UNIFORM
        barrier.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.buffer = self._ubo
        barrier.size = 256
        vk.CmdPipelineBarrier(cmd, STAGE_HOST, STAGE_FRAGMENT, 0, 0, None, 1, _addr(barrier), 0, None)
        clear = VkClearValue()
        clear.color[:] = (0.0, 0.0, 0.0, 0.0)
        rp = VkRenderPassBeginInfo()
        rp.sType = ST_RENDER_PASS_BEGIN
        rp.renderPass = self._render_pass
        rp.framebuffer = self._framebuffers[index.value]
        rp.renderArea.extent = VkExtent2D(*self._extent)
        rp.clearValueCount = 1
        rp.pClearValues = _addr(clear)
        vk.CmdBeginRenderPass(cmd, _addr(rp), 0)
        vk.CmdBindPipeline(cmd, 0, self._pipeline)
        view = VkViewport(0.0, 0.0, float(self._extent[0]), float(self._extent[1]), 0.0, 1.0)
        scissor = VkRect2D(VkOffset2D(0, 0), VkExtent2D(self._extent[0], self._extent[1]))
        self._vk.CmdSetViewport(cmd, 0, 1, c_void_p(ctypes.addressof(view)))
        self._vk.CmdSetScissor(cmd, 0, 1, c_void_p(ctypes.addressof(scissor)))
        self._vbind_keep = (view, scissor)
        if self._layout_sets:
            dset = c_uint64(self._dset)
            vk.CmdBindDescriptorSets(cmd, 0, self._layout, 0, 1, ctypes.cast(byref(dset), c_void_p), 0, None)
        vk.CmdDraw(cmd, 3, 1, 0, 0)
        vk.CmdEndRenderPass(cmd)
        _check(vk.EndCommandBuffer(cmd), "end command")
        wait_sem = c_uint64(self._image_available[frame])
        signal_sem = c_uint64(self._render_finished[frame])
        wait_stage = c_uint32(STAGE_COLOR_OUT)
        cmd_keep = c_void_p(cmd)
        submit = VkSubmitInfo()
        submit.sType = ST_SUBMIT_INFO
        submit.waitSemaphoreCount = 1
        submit.pWaitSemaphores = ctypes.cast(byref(wait_sem), c_void_p)
        submit.pWaitDstStageMask = ctypes.cast(byref(wait_stage), c_void_p)
        submit.commandBufferCount = 1
        submit.pCommandBuffers = ctypes.cast(byref(cmd_keep), c_void_p)
        submit.signalSemaphoreCount = 1
        submit.pSignalSemaphores = ctypes.cast(byref(signal_sem), c_void_p)
        _check(vk.QueueSubmit(self._queue, 1, _addr(submit), fence), "queue submit")
        pixels = None
        if capture and self._can_readback:
            _check(vk.WaitForFences(self._device, 1, byref(c_uint64(fence)), 1, 2_000_000_000), "wait draw")
            pixels = self._read_image(self._images[index.value])
        swap = c_uint64(self._swapchain)
        present = VkPresentInfoKHR()
        present.sType = ST_PRESENT_INFO
        present.waitSemaphoreCount = 1
        present.pWaitSemaphores = ctypes.cast(byref(signal_sem), c_void_p)
        present.swapchainCount = 1
        present.pSwapchains = ctypes.cast(byref(swap), c_void_p)
        present.pImageIndices = ctypes.cast(byref(index), c_void_p)
        presented = vk.QueuePresentKHR(self._queue, _addr(present))
        if presented in (OUT_OF_DATE, SUBOPTIMAL):
            self._resize = True
        elif presented != SUCCESS:
            _check(presented, "present")
        self._frame = (frame + 1) % 2
        self._frame_keep = (begin, barrier, clear, rp, wait_sem, signal_sem, wait_stage, cmd_keep, submit, swap, present, index)
        return pixels

    def _ensure_readback(self):
        byte_count = self._extent[0] * self._extent[1] * 4
        if self._readback_buffer and self._readback_bytes >= byte_count:
            return
        self._destroy_readback()
        buf, mem, size = self._create_buffer(byte_count, 0x2)  # TRANSFER_DST
        ptr = c_void_p()
        _check(self._vk.MapMemory(self._device, mem, 0, size, 0, byref(ptr)), "map readback")
        self._readback_buffer = buf
        self._readback_memory = mem
        self._readback_ptr = ptr
        self._readback_bytes = byte_count

    def _destroy_readback(self):
        if self._readback_memory:
            self._vk.UnmapMemory(self._device, self._readback_memory)
            self._vk.DestroyBuffer(self._device, self._readback_buffer, None)
            self._vk.FreeMemory(self._device, self._readback_memory, None)
        self._readback_buffer = 0
        self._readback_memory = 0
        self._readback_ptr = None
        self._readback_bytes = 0

    def _read_image(self, image):
        self._ensure_readback()
        vk = self._vk
        alloc = VkCommandBufferAllocateInfo()
        alloc.sType = ST_COMMAND_BUFFER_ALLOCATE
        alloc.commandPool = self._pool
        alloc.commandBufferCount = 1
        cmd = c_void_p()
        _check(vk.AllocateCommandBuffers(self._device, _addr(alloc), byref(cmd)), "readback command")
        begin = VkCommandBufferBeginInfo()
        begin.sType = ST_COMMAND_BUFFER_BEGIN
        begin.flags = CMD_ONE_TIME
        _check(vk.BeginCommandBuffer(cmd, _addr(begin)), "begin readback")
        barrier = VkImageMemoryBarrier()
        barrier.sType = ST_IMAGE_MEMORY_BARRIER
        barrier.srcAccessMask = ACCESS_MEMORY_READ
        barrier.dstAccessMask = ACCESS_TRANSFER_READ
        barrier.oldLayout = LAYOUT_PRESENT
        barrier.newLayout = LAYOUT_TRANSFER_SRC
        barrier.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.image = image
        barrier.subresourceRange.aspectMask = IMAGE_ASPECT_COLOR
        barrier.subresourceRange.levelCount = 1
        barrier.subresourceRange.layerCount = 1
        vk.CmdPipelineBarrier(cmd, STAGE_BOTTOM, STAGE_TRANSFER, 0, 0, None, 0, None, 1, _addr(barrier))
        region = VkBufferImageCopy()
        region.imageSubresource.aspectMask = IMAGE_ASPECT_COLOR
        region.imageSubresource.layerCount = 1
        region.imageExtent = VkExtent3D(self._extent[0], self._extent[1], 1)
        vk.CmdCopyImageToBuffer(cmd, image, LAYOUT_TRANSFER_SRC, self._readback_buffer, 1, _addr(region))
        back = VkImageMemoryBarrier()
        back.sType = ST_IMAGE_MEMORY_BARRIER
        back.srcAccessMask = ACCESS_TRANSFER_READ
        back.dstAccessMask = ACCESS_MEMORY_READ
        back.oldLayout = LAYOUT_TRANSFER_SRC
        back.newLayout = LAYOUT_PRESENT
        back.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        back.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        back.image = image
        back.subresourceRange.aspectMask = IMAGE_ASPECT_COLOR
        back.subresourceRange.levelCount = 1
        back.subresourceRange.layerCount = 1
        vk.CmdPipelineBarrier(cmd, STAGE_TRANSFER, STAGE_BOTTOM, 0, 0, None, 0, None, 1, _addr(back))
        _check(vk.EndCommandBuffer(cmd), "end readback")
        submit = VkSubmitInfo()
        submit.sType = ST_SUBMIT_INFO
        submit.commandBufferCount = 1
        submit.pCommandBuffers = ctypes.cast(byref(cmd), c_void_p)
        _check(vk.QueueSubmit(self._queue, 1, _addr(submit), 0), "submit readback")
        _check(vk.QueueWaitIdle(self._queue), "readback idle")
        byte_count = self._extent[0] * self._extent[1] * 4
        raw = ctypes.string_at(self._readback_ptr, byte_count)
        self._read_keep = (alloc, begin, barrier, region, back, submit)
        return self._extent[0], self._extent[1], raw

    def _destroy_window(self):
        if getattr(self, "_window", None) and getattr(self, "_glfw", None):
            self._glfw.glfwDestroyWindow(self._window)
            self._window = None
            self._glfw.glfwTerminate()


def save_png(path, width, height, bgra, swap_rb=True):
    from PIL import Image
    raw = bytearray(bgra)
    if swap_rb:
        for i in range(0, len(raw), 4):
            raw[i], raw[i + 2] = raw[i + 2], raw[i]
    image = Image.frombytes("RGBA", (width, height), bytes(raw))
    image.save(path)
    return image


def glass_metrics(width, height, bgra):
    """Return simple colour stats used to confirm the shader actually drew."""
    def px(x, y):
        i = (y * width + x) * 4
        b, g, r, a = bgra[i:i + 4]
        return r, g, b, a

    # The slope is the bright rim. The clear sample sits in still water
    # between the two darker panels used by the self-test.
    rim = px(width // 2, min(6, height - 1))
    clear = px(width // 2, min(145, height - 1))
    panel = px(width // 2, height // 2)
    corner = px(min(2, width - 1), min(2, height - 1))
    return {"rim": rim, "clear": clear, "panel": panel, "corner": corner}


def run_self_test(png_path=None):
    renderer = LiquidGlassRenderer(720, 440, "MP Liquid Glass self-test")
    try:
        renderer.open()
        if renderer.vendor_id != NVIDIA_VENDOR_ID:
            raise RuntimeError(renderer.summary)
        renderer.set_panels(((60.0, 58.0, 600.0, 52.0), (60.0, 180.0, 600.0, 200.0)))
        pixels = None
        for i in range(6):
            pixels = renderer.draw("dreamworlds_ultra", capture=(i == 5))
        if not pixels:
            raise RuntimeError("NVIDIA swapchain did not produce a readable frame")
        width, height, bgra = pixels
        if png_path:
            save_png(png_path, width, height, bgra, swap_rb=(renderer.format != FORMAT_R8G8B8A8_UNORM))
        if renderer.format == FORMAT_R8G8B8A8_UNORM:
            stats = glass_metrics(width, height, _swap(bgra))
        else:
            stats = glass_metrics(width, height, bgra)
        rim = stats["rim"]
        clear = stats["clear"]
        panel = stats["panel"]
        corner = stats["corner"]
        if max(rim[0], rim[1], rim[2]) < 180:
            raise RuntimeError(f"sloped rim is not catching light: {rim}")
        if min(clear[0], clear[1], clear[2]) < 140:
            raise RuntimeError(f"the water is not clear glass: {clear}")
        if clear[2] < clear[1] + 8:
            raise RuntimeError(f"the still water is missing the dreamworlds theme colour: {clear}")
        clear_luma = clear[0] + clear[1] + clear[2]
        panel_luma = panel[0] + panel[1] + panel[2]
        if panel_luma >= clear_luma:
            raise RuntimeError(f"glass panel is not darker than the water ({panel} vs {clear})")
        if panel_luma < 120:
            raise RuntimeError(f"glass panel is a solid well, not shaded glass: {panel}")
        if max(corner[0], corner[1], corner[2]) > 24:
            raise RuntimeError(f"corner outside the rounded glass is not clear: {corner}")
        if not renderer.shaped:
            raise RuntimeError("the X11 window was not clipped to the rounded glass shape")
        print(
            f"LIQUID_GLASS_OK {renderer.summary} "
            f"frame={width}x{height} rim={rim} water={clear} panel={panel} corner={corner}",
            flush=True,
        )
        return renderer.summary
    finally:
        renderer.close()


def _swap(bgra):
    raw = bytearray(bgra)
    for i in range(0, len(raw), 4):
        raw[i], raw[i + 2] = raw[i + 2], raw[i]
    return bytes(raw)


if __name__ == "__main__":
    try:
        run_self_test()
    except Exception as exc:
        print(f"Liquid Glass: {exc}", file=sys.stderr)
        raise SystemExit(1)
