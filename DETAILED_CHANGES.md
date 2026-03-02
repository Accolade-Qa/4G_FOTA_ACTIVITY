# Code Changes - Detailed Line by Line

## File 1: SerialReader.java

### Change 1.1: Add lastDeviceState field
**Location**: Line 41 (after `lastDeviceId` field)
```java
// ADDED:
private String lastDeviceState = null;
```

### Change 1.2: Update processInternalState() method
**Location**: Lines 148-177
```java
// BEFORE:
private void processInternalState(String line) {
    MessageParser.ParsedInfo info = parser.parse(line);
    if (info != null) {
        if ("SOFTWARE".equals(info.software) && line.toLowerCase().contains("aeplfwver")) {
            this.aeplFwVerFound = true;
            this.lastAeplFwVersion = info.version;
            logger.info("[SR] High-fidelity AEPL FW Version found: {}", info.version);
        }

        this.lastSoftwareVersion = info.version;
        if (!info.software.equals("SOFTWARE") && !info.software.equals("FIRMWARE")) {
            this.lastDeviceId = info.software;
        }
        if (info.loginPacketInfo != null) {
            this.lastLoginPacketInfo = info.loginPacketInfo;
            if (info.loginPacketInfo.imei != null && !info.loginPacketInfo.imei.isEmpty()) {
                logWriter.setImei(info.loginPacketInfo.imei);
            }
        }
        putVersionIntoMap(info.state, info.software, info.version);
    }
}

// AFTER:
private void processInternalState(String line) {
    MessageParser.ParsedInfo info = parser.parse(line);
    if (info != null) {
        if ("SOFTWARE".equals(info.software) && line.toLowerCase().contains("aeplfwver")) {
            this.aeplFwVerFound = true;
            this.lastAeplFwVersion = info.version;
            logger.info("[SR] High-fidelity AEPL FW Version found: {}", info.version);
        }

        this.lastSoftwareVersion = info.version;
        if (!info.software.equals("SOFTWARE") && !info.software.equals("FIRMWARE")) {
            this.lastDeviceId = info.software;
        }
        
        // NEW: Capture device state
        if (info.state != null && !info.state.equals("LOGIN") && !info.state.equals("UNKNOWN")) {
            this.lastDeviceState = info.state;
            logger.debug("[SR] Captured device state: {}", info.state);
            // NEW: Update parser with the latest device state
            parser.setDeviceState(info.state);
        }
        
        if (info.loginPacketInfo != null) {
            this.lastLoginPacketInfo = info.loginPacketInfo;
            if (info.loginPacketInfo.imei != null && !info.loginPacketInfo.imei.isEmpty()) {
                logWriter.setImei(info.loginPacketInfo.imei);
            }
        }
        putVersionIntoMap(info.state, info.software, info.version);
    }
}
```

### Change 1.3: Update resetState() method
**Location**: Lines 208-215
```java
// BEFORE:
public void resetState() {
    this.lastSoftwareVersion = null;
    this.lastAeplFwVersion = null;
    this.lastDownloadProgress = 0.0;
    this.lastLoginPacketInfo = null;
    this.aeplFwVerFound = false;
    logger.info("[SR] State reset for new cycle.");
}

// AFTER:
public void resetState() {
    this.lastSoftwareVersion = null;
    this.lastAeplFwVersion = null;
    this.lastDownloadProgress = 0.0;
    this.lastDeviceState = null;  // NEW
    this.lastLoginPacketInfo = null;
    this.aeplFwVerFound = false;
    parser.setDeviceState(null);  // NEW
    logger.info("[SR] State reset for new cycle.");
}
```

---

## File 2: MessageParser.java

### Change 2.1: Add deviceState field and setter method
**Location**: After line 14 (after IMEI_PATTERN definition)
```java
// ADDED:
// Optional state to use when creating LoginPacketInfo from serial login packets
private String deviceState = null;

// ... existing code ...

/**
 * Sets the current device state captured from serial logs.
 * This state will be used when creating LoginPacketInfo from login packets.
 * 
 * @param state The device state to use
 */
public void setDeviceState(String state) {
    this.deviceState = state;
}
```

### Change 2.2: Update parseLoginPacket() method
**Location**: Lines 205-243 (the login packet parsing section)
```java
// BEFORE:
if (!foundVersion.isEmpty()) {
    // We use null for model and state because they are not present in the login
    // packet.
    // The LoginPacketInfo constructor handles these nulls by setting default
    // values.
    LoginPacketInfo loginInfo = new LoginPacketInfo(imei, iccid, UIN, foundVersion, vin, null, null);
    logger.info("[PARSER] Valid login packet: UIN={}, IMEI={}, Version={}", UIN, imei, foundVersion);
    return new ParsedInfo("LOGIN", UIN, foundVersion, loginInfo);
}

// AFTER:
if (!foundVersion.isEmpty()) {
    // Use the captured device state (if available) instead of null
    // This ensures the login packet is created with the actual device state
    String stateForPacket = (deviceState != null && !deviceState.isEmpty()) ? deviceState : null;
    LoginPacketInfo loginInfo = new LoginPacketInfo(imei, iccid, UIN, foundVersion, vin, null, stateForPacket);
    logger.info("[PARSER] Valid login packet: UIN={}, IMEI={}, Version={}, State={}", UIN, imei, foundVersion, stateForPacket);
    return new ParsedInfo("LOGIN", UIN, foundVersion, loginInfo);
}
```

---

## File 3: FirmwareResolver.java

### Change 3.1: Add extractVersionFromFilename() method
**Location**: After compareVersions() method (around line 175)
```java
// ADDED:
/**
 * Extracts the firmware version from a binary filename.
 * Pattern: ATCU_5.2.8_REL24.bin -> 5.2.8_REL24
 * 
 * @param filename The binary filename
 * @return Extracted version string, or the original filename if extraction fails
 */
private String extractVersionFromFilename(String filename) {
    if (filename == null || filename.isEmpty()) {
        return "";
    }
    
    // Remove directory path if present
    String name = filename.substring(filename.lastIndexOf(java.io.File.separator) + 1);
    
    // Pattern: ATCU_X.X.X_RELMM.bin or similar
    // Remove extension
    if (name.endsWith(".bin")) {
        name = name.substring(0, name.length() - 4);
    }
    
    // Remove prefix (ATCU_)
    if (name.startsWith("ATCU_") || name.startsWith("atcu_")) {
        name = name.substring(5);
    }
    
    // Remove trailing " - Copy" or similar variations
    if (name.contains(" - ")) {
        name = name.substring(0, name.indexOf(" - ")).trim();
    }
    
    logger.debug("[RESOLVER] Extracted version from filename '{}': '{}'", filename, name);
    return name;
}
```

### Change 3.2: Update resolveNextVersion() firmware list building
**Location**: Lines 65-88 (in the firmware array processing loop)
```java
// BEFORE:
JsonNode firmwareArray = stateNode.get("firmware");
if (firmwareArray != null && firmwareArray.isArray()) {
    List<String> versions = new ArrayList<>();
    for (JsonNode fw : firmwareArray) {
        versions.add(fw.get("firmwareVersion").asText().trim());
    }

    logger.debug("[RESOLVER] Found versions in JSON for {}: {}", stateName, versions);

    int currentIndex = -1;
    for (int i = 0; i < versions.size(); i++) {
        if (isSameVersion(versions.get(i), normalizedCurrent)) {
            currentIndex = i;
            break;
        }
    }

// AFTER:
JsonNode firmwareArray = stateNode.get("firmware");
if (firmwareArray != null && firmwareArray.isArray()) {
    List<String> versions = new ArrayList<>();
    List<String> filenames = new ArrayList<>();  // NEW
    for (JsonNode fw : firmwareArray) {
        String filename = fw.get("fileName").asText().trim();  // NEW
        filenames.add(filename);  // NEW
        // Extract binary version from filename (e.g., ATCU_5.2.8_REL24.bin -> 5.2.8_REL24)
        String binaryVersion = extractVersionFromFilename(filename);  // NEW
        versions.add(binaryVersion);  // CHANGED: was fw.get("firmwareVersion")
        logger.debug("[RESOLVER] File: {}, Binary Version: {}", filename, binaryVersion);  // NEW
    }

    logger.debug("[RESOLVER] Found versions in JSON for {}: {}", stateName, versions);

    int currentIndex = -1;
    for (int i = 0; i < versions.size(); i++) {
        if (isSameVersion(versions.get(i), normalizedCurrent)) {
            currentIndex = i;
            break;
        }
    }
```

### Change 3.3: Note on isSameVersion() improvements
**Location**: Lines 154-160
The `isSameVersion()` method comment was updated for clarity:
```java
/**
 * Compares two version strings considering only the major components.
 * 
 * @param v1 First version string
 * @param v2 Second version string
 * @return True if the major version components match (ignoring suffixes like
 *         _REL)
 */
private boolean isSameVersion(String v1, String v2) {
    if (v1 == null || v2 == null)
        return false;
    // Remove all non-numeric and non-dot characters to compare base versions
    // e.g., 5.2.8_REL24 -> 5.2.8 and 5.2.8_REL24 -> 5.2.8 (exact match)
    String s1 = v1.split("_")[0].split("-")[0].trim();
    String s2 = v2.split("_")[0].split("-")[0].trim();
    return s1.equalsIgnoreCase(s2);
}
```

---

## Summary of Changes

| File | Changes | Purpose |
|------|---------|---------|
| SerialReader.java | Added state tracking, updated processInternalState(), modified resetState() | Capture device state from logs and pass to parser |
| MessageParser.java | Added deviceState field and setter, modified parseLoginPacket() | Use captured state when creating login packets |
| FirmwareResolver.java | Added extractVersionFromFilename(), updated firmware list building | Extract real binary versions from filenames for comparison |

**Total Lines Changed**: ~80 lines of code across 3 files
**No Breaking Changes**: All modifications are backward compatible
**Compilation**: ✅ Clean build with no errors
