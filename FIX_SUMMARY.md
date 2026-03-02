# FOTA Activity - Bug Fixes Summary

## Overview
Two critical issues have been identified and fixed in the FOTA automation system:
1. **Login Packet State Defaulting to "Default"** - State field was not capturing device state from serial logs
2. **Version Mismatch in Firmware Resolution** - Device version (5.2.8_REL24) was not matching JSON firmware versions (5.2.11)

---

## Issue 1: Login Packet State Defaulting to "Default"

### Problem
The `login_packets.json` file was always showing `"state": "Default"` instead of the actual device state from serial logs. This happened because:

1. Login packets (55AA format) from the device don't include a state field in their data
2. `MessageParser.parseLoginPacket()` was passing `null` for the state parameter
3. `LoginPacketInfo` constructor defaults null state values to "Default"

### Root Cause Code
**MessageParser.java (original, line 243):**
```java
LoginPacketInfo loginInfo = new LoginPacketInfo(imei, iccid, UIN, foundVersion, vin, null, null);
//                                                                                    ↑    ↑
//                                                                             model, state = null
```

**LoginPacketInfo.java (line 47):**
```java
this.state = (state == null || state.isEmpty()) ? "Default" : state;
```

### Solution Implemented

#### Step 1: Track Device State in SerialReader
Added a field to cache the last known device state captured from serial logs:
- **File**: `SerialReader.java`
- **Change**: Added `private String lastDeviceState = null;`

#### Step 2: Update MessageParser with Device State
Modified `MessageParser` to accept and use the device state:
- **File**: `MessageParser.java`
- **Changes**:
  - Added field: `private String deviceState = null;`
  - Added method: `public void setDeviceState(String state)`
  - Modified `parseLoginPacket()` to use the cached device state when creating `LoginPacketInfo`

**New code:**
```java
String stateForPacket = (deviceState != null && !deviceState.isEmpty()) ? deviceState : null;
LoginPacketInfo loginInfo = new LoginPacketInfo(imei, iccid, UIN, foundVersion, vin, null, stateForPacket);
```

#### Step 3: Update SerialReader to Capture and Pass State
- **File**: `SerialReader.java`
- **Changes**:
  - In `processInternalState()`: Capture state from parsed messages and update the parser:
    ```java
    if (info.state != null && !info.state.equals("LOGIN") && !info.state.equals("UNKNOWN")) {
        this.lastDeviceState = info.state;
        parser.setDeviceState(info.state);  // Pass to parser for next login packet
    }
    ```
  - In `resetState()`: Clear the device state for new cycles

### Statewise-Protocol Abbreviation Handling
An additional parsing enhancement recognises lines containing "statewise prtcl" and extracts a two-letter state code (e.g. `MH`).
- **MessageParser.java** now inspects such lines before normal pattern matching, returning a `ParsedInfo` whose `state` is the abbreviation and `software` set to "STATEWISE".
- **FirmwareResolver.java** gained `resolveStateName(String abbr)` which reads the `stateAbbreviation` field from `servers.json` and caches a lookup table. This method is used by SerialReader and later by Orchestrator to validate/match abbreviations.
- **SerialReader.processInternalState()** detects two-letter states and, if a resolver is available, maps them to full names, logging the mapping result.
- **Orchestrator** additionally normalises `loginInfo.state` by calling the resolver again (to guard against race conditions) and falls back to the default state if mapping fails.
- Unit tests added:
  - `MessageParserTest` checks abbreviation extraction and login-packet state population.
  - `FirmwareResolverTest` verifies `resolveStateName` behaviour.
  - `SerialReaderTest` ensures a parsed abbreviation leads to a mapped state in the persisted login packet.

### Result
When a device sends serial logs with state information (e.g., "STABLE"), that state is now captured and used when the next login packet arrives. The `login_packets.json` will now show the actual device state instead of "Default".

---

## Issue 2: Version Mismatch in Firmware Resolution

### Problem
The firmware resolver was failing to match device versions because it was comparing different version numbering schemes:

**servers.json structure:**
```json
{
  "state": "Bihar",
  "firmware": [
    {
      "firmwareVersion": "5.2.11",      // ← Sequence number
      "fileName": "ATCU_5.2.8_REL24.bin" // ← Actual binary version
    }
  ]
}
```

**Device reports**: `5.2.8_REL24` (from binary filename)
**Resolver tries to match**: `5.2.11` (from firmwareVersion field)
**Result**: "5.2.11" ≠ "5.2.8" → No match → Version comparison fails

### Root Cause Code
**FirmwareResolver.java (original, line 72-74):**
```java
List<String> versions = new ArrayList<>();
for (JsonNode fw : firmwareArray) {
    versions.add(fw.get("firmwareVersion").asText().trim());
    // Uses "5.2.11" instead of actual binary version "5.2.8_REL24"
}
```

**Version comparison (line 82-87):**
```java
if (isSameVersion(versions.get(i), normalizedCurrent)) {
    // isSameVersion("5.2.11", "5.2.8_REL24") 
    // → splits to "5.2.11" vs "5.2.8" → FALSE (no match)
}
```

### Solution Implemented

#### Step 1: Extract Version from Binary Filename
Added a new helper method to extract the actual firmware version from filenames:

**FirmwareResolver.java - New method:**
```java
private String extractVersionFromFilename(String filename) {
    // Input: ATCU_5.2.8_REL24.bin
    // Output: 5.2.8_REL24
    
    String name = filename.substring(filename.lastIndexOf(File.separator) + 1);
    if (name.endsWith(".bin")) {
        name = name.substring(0, name.length() - 4);
    }
    if (name.startsWith("ATCU_") || name.startsWith("atcu_")) {
        name = name.substring(5);
    }
    if (name.contains(" - ")) {
        name = name.substring(0, name.indexOf(" - ")).trim();
    }
    return name;
}
```

#### Step 2: Use Binary Version for Matching
Modified the firmware resolution logic to use extracted binary versions:

**Before:**
```java
versions.add(fw.get("firmwareVersion").asText().trim());
```

**After:**
```java
String filename = fw.get("fileName").asText().trim();
filenames.add(filename);
String binaryVersion = extractVersionFromFilename(filename);
versions.add(binaryVersion);  // Now uses "5.2.8_REL24" instead of "5.2.11"
```

#### Step 3: Improved Version Comparison
The existing `isSameVersion()` method already splits on `_` to extract base versions:
```java
String s1 = v1.split("_")[0].split("-")[0].trim();  // "5.2.8" from "5.2.8_REL24"
String s2 = v2.split("_")[0].split("-")[0].trim();  // "5.2.8" from "5.2.8_REL24"
```

Now this correctly matches device version "5.2.8_REL24" with JSON entry having binary version "5.2.8_REL24".

### Result
#### Before Fix:
```
Device version: 5.2.8_REL24
JSON firmware: 5.2.11 with file ATCU_5.2.8_REL24.bin
Comparison: "5.2.11" vs "5.2.8_REL24" → NO MATCH
Result: Wrong version selected or fallback logic triggered
```

#### After Fix:
```
Device version: 5.2.8_REL24
JSON firmware: 5.2.11 with file ATCU_5.2.8_REL24.bin
Extracted version: 5.2.8_REL24
Comparison: "5.2.8_REL24" vs "5.2.8_REL24" → MATCH!
Result: Correct next version in sequence is selected
```

---

## Files Modified

### 1. SerialReader.java
- Added `lastDeviceState` field to track device state
- Modified `processInternalState()` to capture state and update parser
- Modified `resetState()` to clear device state

### 2. MessageParser.java
- Added `deviceState` field
- Added `setDeviceState(String state)` public method
- Modified `parseLoginPacket()` to use captured device state

### 3. FirmwareResolver.java
- Added `extractVersionFromFilename()` helper method
- Modified version list building to extract binary versions from filenames
- Enhanced logging with filename and extracted version info

---

## Testing & Validation

### Compilation
✅ Code compiles successfully without errors
✅ All dependencies resolved
✅ No breaking changes to public APIs

### Expected Behavior After Fix

1. **State Capture**:
   - Device sends state in log messages (e.g., "STATE=STABLE")
   - SerialReader captures and caches this state
   - Next login packet includes the captured state
   - `login_packets.json` shows actual device state instead of "Default"

2. **Version Matching**:
   - Device reports: "5.2.8_REL24"
   - Resolver extracts "5.2.8_REL24" from JSON filename
   - Versions match correctly
   - Correct next firmware version is selected

---

## Recommendations

1. **Verify Serial Format**: Ensure devices send state information in their log messages. If not, consider adding support for it or using a state configuration file.

2. **Standardize servers.json**: Consider adding a separate `binaryVersion` field to servers.json for clarity:
   ```json
   {
     "firmwareVersion": "5.2.11",
     "binaryVersion": "5.2.8_REL24",
     "fileName": "ATCU_5.2.8_REL24.bin"
   }
   ```

3. **Logging**: Monitor the logs for:
   - `[SR] Captured device state:` messages to verify state capture
   - `[RESOLVER] Extracted version from filename:` messages to verify version extraction
   - `[RESOLVER] Current version matched JSON at index` to verify correct matching

4. **Testing**: Create test cases for:
   - LoginPacketInfo with captured state
   - FirmwareResolver with various filename patterns
   - Version comparison with REL suffixes
