#!/usr/bin/env python3
"""
Generates ios/DirectInvestTracker.xcodeproj/project.pbxproj
plus Info.plist and Assets.xcassets stubs.

Run from the repo root:
    python3 generate_xcodeproj.py
"""
import hashlib
import os

SOURCE_DIR   = "ios/DirectInvestTracker"
XCODEPROJ    = "ios/DirectInvestTracker.xcodeproj"
BUNDLE_ID    = "com.quantformity.directinvest"
PRODUCT_NAME = "DirectInvestTracker"
IOS_VERSION  = "17.0"
BGTASK_ID    = "com.quantformity.directinvest.marketrefresh"

# ── UUID helpers ─────────────────────────────────────────────────────────────

def uid(seed: str) -> str:
    """Deterministic 24-char uppercase hex from seed string."""
    return hashlib.md5(seed.encode()).hexdigest().upper()[:24]

# ── Fixed UUIDs ──────────────────────────────────────────────────────────────

PROJ_UID             = uid("project")
MAIN_GROUP_UID       = uid("maingroup")
PRODUCTS_GROUP_UID   = uid("productsgroup")
APP_PRODUCT_UID      = uid("appproduct")
SOURCES_PHASE_UID    = uid("sourcesphase")
FRAMEWORKS_PHASE_UID = uid("frameworksphase")
RESOURCES_PHASE_UID  = uid("resourcesphase")
NATIVE_TARGET_UID    = uid("nativetarget")
DEBUG_PROJ_UID       = uid("debugconfigproj")
RELEASE_PROJ_UID     = uid("releaseconfigproj")
CL_PROJ_UID          = uid("configlistproj")
DEBUG_TARGET_UID     = uid("debugconfigtarget")
RELEASE_TARGET_UID   = uid("releaseconfigtarget")
CL_TARGET_UID        = uid("configlisttarget")
INFO_PLIST_UID       = uid("infoplist")
ASSETS_UID           = uid("assetsxcassets")

# ── Collect Swift files ───────────────────────────────────────────────────────

swift_files = []  # list of (rel_path_from_source_dir, filename)
for root, dirs, files in os.walk(SOURCE_DIR):
    dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
    for f in sorted(files):
        if f.endswith('.swift'):
            rel = os.path.relpath(os.path.join(root, f), SOURCE_DIR)
            swift_files.append((rel, f))

# ── Build group tree ──────────────────────────────────────────────────────────

# Map folder path → list of children (file rels or sub-folder paths)
folders: dict[str, list] = {}
for rel, fname in swift_files:
    folder = os.path.dirname(rel) or "."
    parts = folder.split(os.sep) if folder != "." else []
    # Ensure every ancestor folder exists in the map
    for depth in range(len(parts) + 1):
        key = os.sep.join(parts[:depth]) if depth > 0 else "."
        if key not in folders:
            folders[key] = []
    # Register file under its direct parent
    parent = os.sep.join(parts) if parts else "."
    folders[parent].append(("file", rel, fname))

# Register sub-folders under their parent
for folder in list(folders.keys()):
    if folder == ".":
        continue
    parent_parts = folder.split(os.sep)[:-1]
    parent = os.sep.join(parent_parts) if parent_parts else "."
    if ("dir", folder) not in folders[parent]:
        folders[parent].append(("dir", folder))

def group_uid_for(folder: str) -> str:
    return uid(f"group:{folder}")

def fref_uid(rel: str) -> str:
    return uid(f"fileref:{rel}")

def bfile_uid(rel: str) -> str:
    return uid(f"buildfile:{rel}")

# ── Emit pbxproj sections ─────────────────────────────────────────────────────

lines: list[str] = []

def L(s=""):
    lines.append(s)

L("// !$*UTF8*$!")
L("{")
L("\tarchiveVersion = 1;")
L("\tclasses = {")
L("\t};")
L("\tobjectVersion = 77;")
L("\tobjects = {")
L()

# ── PBXBuildFile ─────────────────────────────────────────────────────────────
L("/* Begin PBXBuildFile section */")
for rel, fname in swift_files:
    L(f"\t\t{bfile_uid(rel)} /* {fname} in Sources */ = {{isa = PBXBuildFile; fileRef = {fref_uid(rel)} /* {fname} */; }};")
L(f"\t\t{uid('assets_build')} /* Assets.xcassets in Resources */ = {{isa = PBXBuildFile; fileRef = {ASSETS_UID} /* Assets.xcassets */; }};")
L("/* End PBXBuildFile section */")
L()

# ── PBXFileReference ──────────────────────────────────────────────────────────
L("/* Begin PBXFileReference section */")
L(f"\t\t{APP_PRODUCT_UID} /* {PRODUCT_NAME}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = {PRODUCT_NAME}.app; sourceTree = BUILT_PRODUCTS_DIR; }};")
L(f"\t\t{INFO_PLIST_UID} /* Info.plist */ = {{isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = \"<group>\"; }};")
L(f"\t\t{ASSETS_UID} /* Assets.xcassets */ = {{isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = Assets.xcassets; sourceTree = \"<group>\"; }};")
for rel, fname in swift_files:
    L(f"\t\t{fref_uid(rel)} /* {fname} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {fname}; sourceTree = \"<group>\"; }};")
L("/* End PBXFileReference section */")
L()

# ── PBXFrameworksBuildPhase ───────────────────────────────────────────────────
L("/* Begin PBXFrameworksBuildPhase section */")
L(f"\t\t{FRAMEWORKS_PHASE_UID} /* Frameworks */ = {{")
L("\t\t\tisa = PBXFrameworksBuildPhase;")
L("\t\t\tbuildActionMask = 2147483647;")
L("\t\t\tfiles = (")
L("\t\t\t);")
L("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
L("\t\t};")
L("/* End PBXFrameworksBuildPhase section */")
L()

# ── PBXGroup ──────────────────────────────────────────────────────────────────
L("/* Begin PBXGroup section */")

def emit_group(folder: str, path_component: str, source_tree: str = "\"<group>\""):
    gid = group_uid_for(folder)
    children = folders.get(folder, [])
    L(f"\t\t{gid} /* {os.path.basename(folder) if folder != '.' else PRODUCT_NAME} */ = {{")
    L("\t\t\tisa = PBXGroup;")
    L("\t\t\tchildren = (")
    for child in children:
        if child[0] == "dir":
            sub_folder = child[1]
            L(f"\t\t\t\t{group_uid_for(sub_folder)} /* {os.path.basename(sub_folder)} */,")
        else:
            _, rel, fname = child
            L(f"\t\t\t\t{fref_uid(rel)} /* {fname} */,")
    L("\t\t\t);")
    if path_component:
        L(f"\t\t\tpath = {path_component};")
    L(f"\t\t\tsourceTree = {source_tree};")
    L("\t\t};")

# Main group
L(f"\t\t{MAIN_GROUP_UID} /* {PRODUCT_NAME} */ = {{")
L("\t\t\tisa = PBXGroup;")
L("\t\t\tchildren = (")
L(f"\t\t\t\t{group_uid_for('.')} /* {PRODUCT_NAME} */,")
L(f"\t\t\t\t{INFO_PLIST_UID} /* Info.plist */,")
L(f"\t\t\t\t{ASSETS_UID} /* Assets.xcassets */,")
L(f"\t\t\t\t{PRODUCTS_GROUP_UID} /* Products */,")
L("\t\t\t);")
L(f"\t\t\tsourceTree = \"<group>\";")
L("\t\t};")

# Products group
L(f"\t\t{PRODUCTS_GROUP_UID} /* Products */ = {{")
L("\t\t\tisa = PBXGroup;")
L("\t\t\tchildren = (")
L(f"\t\t\t\t{APP_PRODUCT_UID} /* {PRODUCT_NAME}.app */,")
L("\t\t\t);")
L("\t\t\tname = Products;")
L(f"\t\t\tsourceTree = \"<group>\";")
L("\t\t};")

# Emit all folder groups
for folder in sorted(folders.keys()):
    path_comp = os.path.basename(folder) if folder != "." else PRODUCT_NAME
    src_tree = "\"<group>\""
    emit_group(folder, path_comp, src_tree)

L("/* End PBXGroup section */")
L()

# ── PBXNativeTarget ───────────────────────────────────────────────────────────
L("/* Begin PBXNativeTarget section */")
L(f"\t\t{NATIVE_TARGET_UID} /* {PRODUCT_NAME} */ = {{")
L("\t\t\tisa = PBXNativeTarget;")
L(f"\t\t\tbuildConfigurationList = {CL_TARGET_UID} /* Build configuration list for PBXNativeTarget \"{PRODUCT_NAME}\" */;")
L("\t\t\tbuildPhases = (")
L(f"\t\t\t\t{SOURCES_PHASE_UID} /* Sources */,")
L(f"\t\t\t\t{FRAMEWORKS_PHASE_UID} /* Frameworks */,")
L(f"\t\t\t\t{RESOURCES_PHASE_UID} /* Resources */,")
L("\t\t\t);")
L("\t\t\tbuildRules = (")
L("\t\t\t);")
L("\t\t\tdependencies = (")
L("\t\t\t);")
L(f"\t\t\tname = {PRODUCT_NAME};")
L(f"\t\t\tpackageProductDependencies = (")
L("\t\t\t);")
L(f"\t\t\tproductName = {PRODUCT_NAME};")
L(f"\t\t\tproductReference = {APP_PRODUCT_UID} /* {PRODUCT_NAME}.app */;")
L("\t\t\tproductType = \"com.apple.product-type.application\";")
L("\t\t};")
L("/* End PBXNativeTarget section */")
L()

# ── PBXProject ────────────────────────────────────────────────────────────────
L("/* Begin PBXProject section */")
L(f"\t\t{PROJ_UID} /* Project object */ = {{")
L("\t\t\tisa = PBXProject;")
L("\t\t\tattributes = {")
L("\t\t\t\tBuildIndependentTargetsInParallel = 1;")
L(f"\t\t\t\tLastSwiftUpdateCheck = 1540;")
L(f"\t\t\t\tLastUpgradeCheck = 1540;")
L("\t\t\t\tTargetAttributes = {")
L(f"\t\t\t\t\t{NATIVE_TARGET_UID} = {{")
L("\t\t\t\t\t\tCreatedOnToolsVersion = 15.4;")
L("\t\t\t\t\t};")
L("\t\t\t\t};")
L("\t\t\t};")
L(f"\t\t\tbuildConfigurationList = {CL_PROJ_UID} /* Build configuration list for PBXProject \"{PRODUCT_NAME}\" */;")
L("\t\t\tcompatibilityVersion = \"Xcode 14.0\";")
L("\t\t\tdevelopmentRegion = en;")
L("\t\t\thasScannedForEncodings = 0;")
L("\t\t\tknownRegions = (")
L("\t\t\t\ten,")
L("\t\t\t\tBase,")
L("\t\t\t);")
L(f"\t\t\tmainGroup = {MAIN_GROUP_UID};")
L(f"\t\t\tproductsGroup = {PRODUCTS_GROUP_UID} /* Products */;")
L("\t\t\tprojectDirPath = \"\";")
L("\t\t\tprojectRoot = \"\";")
L("\t\t\ttargets = (")
L(f"\t\t\t\t{NATIVE_TARGET_UID} /* {PRODUCT_NAME} */,")
L("\t\t\t);")
L("\t\t};")
L("/* End PBXProject section */")
L()

# ── PBXResourcesBuildPhase ────────────────────────────────────────────────────
L("/* Begin PBXResourcesBuildPhase section */")
L(f"\t\t{RESOURCES_PHASE_UID} /* Resources */ = {{")
L("\t\t\tisa = PBXResourcesBuildPhase;")
L("\t\t\tbuildActionMask = 2147483647;")
L("\t\t\tfiles = (")
L(f"\t\t\t\t{uid('assets_build')} /* Assets.xcassets in Resources */,")
L("\t\t\t);")
L("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
L("\t\t};")
L("/* End PBXResourcesBuildPhase section */")
L()

# ── PBXSourcesBuildPhase ──────────────────────────────────────────────────────
L("/* Begin PBXSourcesBuildPhase section */")
L(f"\t\t{SOURCES_PHASE_UID} /* Sources */ = {{")
L("\t\t\tisa = PBXSourcesBuildPhase;")
L("\t\t\tbuildActionMask = 2147483647;")
L("\t\t\tfiles = (")
for rel, fname in swift_files:
    L(f"\t\t\t\t{bfile_uid(rel)} /* {fname} in Sources */,")
L("\t\t\t);")
L("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
L("\t\t};")
L("/* End PBXSourcesBuildPhase section */")
L()

# ── XCBuildConfiguration ─────────────────────────────────────────────────────
common_target = {
    "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
    "ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME": "AccentColor",
    "CODE_SIGN_STYLE": "Automatic",
    "CURRENT_PROJECT_VERSION": "1",
    "GENERATE_INFOPLIST_FILE": "NO",
    "INFOPLIST_FILE": "DirectInvestTracker/Info.plist",
    "IPHONEOS_DEPLOYMENT_TARGET": IOS_VERSION,
    "MARKETING_VERSION": "1.0",
    "PRODUCT_BUNDLE_IDENTIFIER": BUNDLE_ID,
    "PRODUCT_NAME": "$(TARGET_NAME)",
    "SWIFT_EMIT_LOC_STRINGS": "YES",
    "SWIFT_VERSION": "5.0",
    "TARGETED_DEVICE_FAMILY": '"1,2"',
}

L("/* Begin XCBuildConfiguration section */")

def emit_config(config_uid, name, is_target, extra=None):
    L(f"\t\t{config_uid} /* {name} */ = {{")
    L("\t\t\tisa = XCBuildConfiguration;")
    L("\t\t\tbuildSettings = {")
    if is_target:
        for k, v in common_target.items():
            L(f"\t\t\t\t{k} = {v};")
        if name == "Debug":
            L("\t\t\t\tDEBUG_INFORMATION_FORMAT = dwarf;")
            L("\t\t\t\tENABLE_TESTABILITY = YES;")
            L('\t\t\t\tONLY_ACTIVE_ARCH = YES;')
            L('\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;')
            L('\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = "-Onone";')
        else:
            L("\t\t\t\tDEBUG_INFORMATION_FORMAT = \"dwarf-with-dsym\";")
            L('\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = "-O";')
            L('\t\t\t\tVALIDATE_PRODUCT = YES;')
    else:
        # Project-level
        L('\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;')
        L('\t\t\t\tCLANG_ANALYZER_NONNULL = YES;')
        L('\t\t\t\tCLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;')
        L('\t\t\t\tCLANG_CXX_LANGUAGE_STANDARD = "gnu++20";')
        L('\t\t\t\tCLANG_ENABLE_MODULES = YES;')
        L('\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;')
        L('\t\t\t\tCLANG_ENABLE_OBJC_WEAK = YES;')
        L('\t\t\t\tCLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;')
        L('\t\t\t\tCLANG_WARN_BOOL_CONVERSION = YES;')
        L('\t\t\t\tCLANG_WARN_COMMA = YES;')
        L('\t\t\t\tCLANG_WARN_CONSTANT_CONVERSION = YES;')
        L('\t\t\t\tCLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;')
        L('\t\t\t\tCLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;')
        L('\t\t\t\tCLANG_WARN_DOCUMENTATION_COMMENTS = YES;')
        L('\t\t\t\tCLANG_WARN_EMPTY_BODY = YES;')
        L('\t\t\t\tCLANG_WARN_ENUM_CONVERSION = YES;')
        L('\t\t\t\tCLANG_WARN_INFINITE_RECURSION = YES;')
        L('\t\t\t\tCLANG_WARN_INT_CONVERSION = YES;')
        L('\t\t\t\tCLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;')
        L('\t\t\t\tCLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;')
        L('\t\t\t\tCLANG_WARN_OBJC_LITERAL_CONVERSION = YES;')
        L('\t\t\t\tCLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;')
        L('\t\t\t\tCLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;')
        L('\t\t\t\tCLANG_WARN_RANGE_LOOP_ANALYSIS = YES;')
        L('\t\t\t\tCLANG_WARN_STRICT_PROTOTYPES = YES;')
        L('\t\t\t\tCLANG_WARN_SUSPICIOUS_MOVE = YES;')
        L('\t\t\t\tCLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;')
        L('\t\t\t\tCLANG_WARN_UNREACHABLE_CODE = YES;')
        L('\t\t\t\tCLANG_WARN__DUPLICATE_METHOD_MATCH = YES;')
        L('\t\t\t\tCOPY_PHASE_STRIP = NO;')
        L(f'\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = {IOS_VERSION};')
        if name == "Debug":
            L('\t\t\t\tDEBUG_INFORMATION_FORMAT = dwarf;')
            L('\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;')
            L('\t\t\t\tENABLE_TESTABILITY = YES;')
            L('\t\t\t\tGCC_C_LANGUAGE_STANDARD = gnu17;')
            L('\t\t\t\tGCC_DYNAMIC_NO_PIC = NO;')
            L('\t\t\t\tGCC_NO_COMMON_BLOCKS = YES;')
            L('\t\t\t\tGCC_OPTIMIZATION_LEVEL = 0;')
            L('\t\t\t\tGCC_PREPROCESSOR_DEFINITIONS = ("DEBUG=1", "$(inherited)");')
            L('\t\t\t\tGCC_WARN_64_TO_32_BIT_CONVERSION = YES;')
            L('\t\t\t\tGCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;')
            L('\t\t\t\tGCC_WARN_UNDECLARED_SELECTOR = YES;')
            L('\t\t\t\tGCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;')
            L('\t\t\t\tGCC_WARN_UNUSED_FUNCTION = YES;')
            L('\t\t\t\tGCC_WARN_UNUSED_VARIABLE = YES;')
            L('\t\t\t\tMTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;')
            L('\t\t\t\tMTL_FAST_MATH = YES;')
            L('\t\t\t\tONLY_ACTIVE_ARCH = YES;')
            L('\t\t\t\tSDKROOT = iphoneos;')
            L('\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;')
        else:
            L('\t\t\t\tDEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";')
            L('\t\t\t\tENABLE_NS_ASSERTIONS = NO;')
            L('\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;')
            L('\t\t\t\tGCC_C_LANGUAGE_STANDARD = gnu17;')
            L('\t\t\t\tGCC_NO_COMMON_BLOCKS = YES;')
            L('\t\t\t\tGCC_WARN_64_TO_32_BIT_CONVERSION = YES;')
            L('\t\t\t\tGCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;')
            L('\t\t\t\tGCC_WARN_UNDECLARED_SELECTOR = YES;')
            L('\t\t\t\tGCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;')
            L('\t\t\t\tGCC_WARN_UNUSED_FUNCTION = YES;')
            L('\t\t\t\tGCC_WARN_UNUSED_VARIABLE = YES;')
            L('\t\t\t\tMTL_FAST_MATH = YES;')
            L('\t\t\t\tSDKROOT = iphoneos;')
            L('\t\t\t\tVALIDATE_PRODUCT = YES;')
    L("\t\t\t};")
    L(f"\t\t\tname = {name};")
    L("\t\t};")

emit_config(DEBUG_PROJ_UID,    "Debug",   is_target=False)
emit_config(RELEASE_PROJ_UID,  "Release", is_target=False)
emit_config(DEBUG_TARGET_UID,  "Debug",   is_target=True)
emit_config(RELEASE_TARGET_UID,"Release", is_target=True)

L("/* End XCBuildConfiguration section */")
L()

# ── XCConfigurationList ───────────────────────────────────────────────────────
L("/* Begin XCConfigurationList section */")
L(f"\t\t{CL_PROJ_UID} /* Build configuration list for PBXProject \"{PRODUCT_NAME}\" */ = {{")
L("\t\t\tisa = XCConfigurationList;")
L("\t\t\tbuildConfigurations = (")
L(f"\t\t\t\t{DEBUG_PROJ_UID} /* Debug */,")
L(f"\t\t\t\t{RELEASE_PROJ_UID} /* Release */,")
L("\t\t\t);")
L("\t\t\tdefaultConfigurationIsVisible = 0;")
L("\t\t\tdefaultConfigurationName = Release;")
L("\t\t};")
L(f"\t\t{CL_TARGET_UID} /* Build configuration list for PBXNativeTarget \"{PRODUCT_NAME}\" */ = {{")
L("\t\t\tisa = XCConfigurationList;")
L("\t\t\tbuildConfigurations = (")
L(f"\t\t\t\t{DEBUG_TARGET_UID} /* Debug */,")
L(f"\t\t\t\t{RELEASE_TARGET_UID} /* Release */,")
L("\t\t\t);")
L("\t\t\tdefaultConfigurationIsVisible = 0;")
L("\t\t\tdefaultConfigurationName = Release;")
L("\t\t};")
L("/* End XCConfigurationList section */")
L()

L("\t};")
L(f"\trootObject = {PROJ_UID} /* Project object */;")
L("}")

# ── Write project.pbxproj ─────────────────────────────────────────────────────

os.makedirs(XCODEPROJ, exist_ok=True)
pbxproj_path = os.path.join(XCODEPROJ, "project.pbxproj")
with open(pbxproj_path, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"✓ Written {pbxproj_path}  ({len(swift_files)} Swift files)")

# ── Info.plist ────────────────────────────────────────────────────────────────

info_plist_path = os.path.join(SOURCE_DIR, "Info.plist")
if not os.path.exists(info_plist_path):
    info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>BGTaskSchedulerPermittedIdentifiers</key>
\t<array>
\t\t<string>{BGTASK_ID}</string>
\t</array>
\t<key>CFBundleDevelopmentRegion</key>
\t<string>$(DEVELOPMENT_LANGUAGE)</string>
\t<key>CFBundleDisplayName</key>
\t<string>DirectInvest</string>
\t<key>CFBundleExecutable</key>
\t<string>$(EXECUTABLE_NAME)</string>
\t<key>CFBundleIdentifier</key>
\t<string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
\t<key>CFBundleInfoDictionaryVersion</key>
\t<string>6.0</string>
\t<key>CFBundleName</key>
\t<string>$(PRODUCT_NAME)</string>
\t<key>CFBundlePackageType</key>
\t<string>$(PRODUCT_BUNDLE_PACKAGE_TYPE)</string>
\t<key>CFBundleShortVersionString</key>
\t<string>$(MARKETING_VERSION)</string>
\t<key>CFBundleVersion</key>
\t<string>$(CURRENT_PROJECT_VERSION)</string>
\t<key>LSRequiresIPhoneOS</key>
\t<true/>
\t<key>UIApplicationSceneManifest</key>
\t<dict>
\t\t<key>UIApplicationSupportsMultipleScenes</key>
\t\t<false/>
\t</dict>
\t<key>UILaunchScreen</key>
\t<dict/>
\t<key>UISupportedInterfaceOrientations</key>
\t<array>
\t\t<string>UIInterfaceOrientationPortrait</string>
\t\t<string>UIInterfaceOrientationLandscapeLeft</string>
\t\t<string>UIInterfaceOrientationLandscapeRight</string>
\t</array>
\t<key>UISupportedInterfaceOrientations~ipad</key>
\t<array>
\t\t<string>UIInterfaceOrientationPortrait</string>
\t\t<string>UIInterfaceOrientationPortraitUpsideDown</string>
\t\t<string>UIInterfaceOrientationLandscapeLeft</string>
\t\t<string>UIInterfaceOrientationLandscapeRight</string>
\t</array>
</dict>
</plist>
"""
    with open(info_plist_path, "w") as f:
        f.write(info_plist)
    print(f"✓ Written {info_plist_path}")
else:
    print(f"  Skipped {info_plist_path} (already exists)")

# ── Assets.xcassets ───────────────────────────────────────────────────────────

assets_dir = os.path.join(SOURCE_DIR, "Assets.xcassets")
os.makedirs(assets_dir, exist_ok=True)
contents_json = os.path.join(assets_dir, "Contents.json")
if not os.path.exists(contents_json):
    with open(contents_json, "w") as f:
        f.write('{\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n')
    print(f"✓ Written {contents_json}")

# AppIcon stub
appicon_dir = os.path.join(assets_dir, "AppIcon.appiconset")
os.makedirs(appicon_dir, exist_ok=True)
appicon_contents = os.path.join(appicon_dir, "Contents.json")
if not os.path.exists(appicon_contents):
    with open(appicon_contents, "w") as f:
        f.write('{\n  "images" : [],\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n')
    print(f"✓ Written {appicon_contents}")

print("\nDone! Open ios/DirectInvestTracker.xcodeproj in Xcode and press Cmd+B.")
