# Issue Analysis: Login Packet State and Version Mismatch

## Issue 1: State Field Defaulting to "Default"

### Root Cause
In `MessageParser.parseLoginPacket()` (line 180):
```java
LoginPacketInfo loginInfo = new LoginPacketInfo(imei, iccid, UIN, foundVersion, vin, null, null);
```

The login packet format from serial port contains 9 fields extracted as parts[0-8]:
- parts[4] = IMEI
- parts[5] = ICCID
- parts[6] = UIN
- parts[7] = Version (e.g., "5.2.8_REL24")
- parts[8] = VIN

**The login packet does NOT contain a STATE field**, so `null` is passed for state.

In `LoginPacketInfo` constructor (line 47):
```java
this.state = (state == null || state.isEmpty()) ? "Default" : state;
```

This defaults to "Default" since state is null.

### Solution 1a: Extract state from serial port data
If the device sends state separately in a different message, the state should be extracted and passed to LoginPacketInfo.

### Solution 1b: Use the latest known state from SerialReader
Modify the code to capture the state from the last parsed message before creating LoginPacketInfo.

---

## Issue 2: Version Mismatch in Firmware Resolution

### Root Cause
**servers.json structure mismatch:**
```json
{
  "state": "Bihar",
  "firmware": [
    {
      "firmwareVersion": "5.2.11",
      "fileName": "ATCU_5.2.8_REL24.bin"
    }
  ]
}
```

The device reports version `5.2.8_REL24` (extracted from serial port), but:
1. `FirmwareResolver.resolveNextVersion()` tries to match against `firmwareVersion` field ("5.2.11")
2. `isSameVersion()` compares:
   - `v1 = "5.2.11"` (from JSON firmwareVersion)
   - `v2 = "5.2.8_REL24"` (from device)
   - After stripping suffixes: "5.2.11" ≠ "5.2.8" → **NO MATCH**

### The Problem
- **Actual firmware binary version**: 5.2.8_REL24 (from filename)
- **Sequence number in firmwareVersion**: 5.2.11 (abstract sequence number)
- **Device reports**: 5.2.8_REL24
- **Comparison fails** because "5.2.11" and "5.2.8" don't match

### Solution 2: Extract version from filename in servers.json
Modify `FirmwareResolver` to extract the actual binary version from the filename instead of using the abstract `firmwareVersion` field.

**Current filename pattern**: `ATCU_5.2.8_REL24.bin`
**Extraction needed**: Extract "5.2.8_REL24" from filename for version matching

---

## Recommended Fixes

### Fix 1: Update LoginPacketInfo state handling
Track the state separately in SerialReader and pass it when creating LoginPacketInfo.

### Fix 2: Update FirmwareResolver to use filename for version matching
Extract the actual firmware version from the binary filename in servers.json instead of relying on the `firmwareVersion` field for comparison.
