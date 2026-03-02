# Testing & Verification Guide

## How to Verify the Fixes

### Part 1: State Capture Verification

#### What to Look For in Logs
The system should now log state capture operations. Monitor your serial logs for these messages:

```
[SR] Captured device state: <STATE_VALUE>
[SR] Captured device state: STABLE
[SR] Captured device state: MAINTENANCE
```

#### Test Steps
1. Start the FOTA automation
2. Ensure device sends state information in serial logs.  This can be either a standard
   `STATE=...` message or the dedicated statewise protocol line such as
   `.  statewise prtcl    |  SWEMP     MH  - MH is abbreviation`.
   The parser will extract the two-letter code and map it using `servers.json`.
3. Check the generated `login_packets.json` file
4. **Expected Result**: `"state"` field should show the captured state, NOT "Default"

#### Example Output - Before Fix
```json
[
  {
    "imei": "861564061380138",
    "iccid": "89916420534724851291",
    "uin": "ACON4NA082300092233",
    "version": "5.2.9_REL06",
    "vin": "ACCDEV07241580138",
    "model": "4G",
    "state": "Default"  ❌ WRONG
  }
]
```

#### Example Output - After Fix
```json
[
  {
    "imei": "861564061380138",
    "iccid": "89916420534724851291",
    "uin": "ACON4NA082300092233",
    "version": "5.2.8_REL24",  ✅ Now matches device version
    "vin": "ACCDEV07241580138",
    "model": "4G",
    "state": "STABLE"  ✅ CORRECT - captured from device logs
  }
]
```

---

### Part 2: Version Matching Verification

#### What to Look For in Logs
The system should now log version extraction and matching. Monitor your logs for:

```
[RESOLVER] File: ATCU_5.2.8_REL24.bin, Binary Version: 5.2.8_REL24
[RESOLVER] Resolving next version for State: 'STABLE', Current Version: '5.2.8_REL24'
[RESOLVER] Current version '5.2.8_REL24' matched JSON at index X. Selecting next in sequence: 'Y'
```

#### Test Steps
1. Ensure your device reports version: `5.2.8_REL24`
2. Check that servers.json has this firmware configured with a filename like `ATCU_5.2.8_REL24.bin`
3. Run the firmware resolver
4. **Expected Result**: Version should match correctly and next firmware version selected

#### Example Version Matching - Before Fix
```
Device version: 5.2.8_REL24
JSON firmwareVersion: 5.2.11
Comparison: "5.2.11" vs "5.2.8" 
Result: ❌ NO MATCH - Falls back to numerical comparison (WRONG!)
```

#### Example Version Matching - After Fix
```
Device version: 5.2.8_REL24
JSON fileName: ATCU_5.2.8_REL24.bin
Extracted version: 5.2.8_REL24
Comparison: "5.2.8_REL24" vs "5.2.8_REL24"
Result: ✅ EXACT MATCH - Correct next version selected!
```

---

## Debugging Tips

### Enable Debug Logging
Add these to your log4j2.xml to see detailed information:

```xml
<Logger name="com.aepl.atcu.SerialReader" level="DEBUG" />
<Logger name="com.aepl.atcu.logic.MessageParser" level="DEBUG" />
<Logger name="com.aepl.atcu.logic.FirmwareResolver" level="DEBUG" />
```

### Check State Capture
Look for these patterns in the raw serial logs from your device:
- `STATE=STABLE`
- `STATE=MAINTENANCE`
- `STATE=IDLE`
- Or similar state identifiers transmitted by your device

If you don't see state information, you may need to:
1. Send a command to the device to make it output state
2. Check device firmware/documentation for state output format
3. Verify the STATE_PATTERN regex in MessageParser matches your format

### Check Version Extraction
Look for this pattern in servers.json filenames:
- `ATCU_X.X.X_RELMM.bin` (standard pattern)
- `ATCU_5.2.8_REL24.bin` ✅ Will extract: 5.2.8_REL24
- `ATCU_5.2.9_REL06 - Copy.bin` ✅ Will extract: 5.2.9_REL06

If your filenames follow a different pattern, you may need to adjust `extractVersionFromFilename()`.

---

## Monitor These Log Messages

### Critical Messages to Check

1. **State Capture** (from SerialReader):
   ```
   [SR] Captured device state: STABLE
   ```
   - ✅ This means device state was successfully captured
   - ❌ If missing, device may not be sending state info

2. **Version Extraction** (from FirmwareResolver):
   ```
   [RESOLVER] File: ATCU_5.2.8_REL24.bin, Binary Version: 5.2.8_REL24
   ```
   - ✅ Shows the extracted version matches filename
   - ❌ If version looks wrong, check file naming pattern

3. **Version Matching Success** (from FirmwareResolver):
   ```
   [RESOLVER] Current version '5.2.8_REL24' matched JSON at index 0. Selecting next: '5.2.9_REL07'
   ```
   - ✅ Version matched and next version is ready
   - ❌ If you see "not found" message, versions don't match

4. **Login Packet Recording** (from LoginPacketStore):
   ```
   Appended login packet for UIN=ACON4NA082300092233 version=5.2.8_REL24 to results/login_packets.json
   ```
   - ✅ Login packet saved successfully with correct version

---

## Troubleshooting

### Issue: State still shows "Default"
**Causes:**
- Device is not sending state information
- State format doesn't match STATE_PATTERN regex
- State is sent AFTER login packet (timing issue)

**Fix:**
1. Check device logs for state information format
2. Update STATE_PATTERN in MessageParser if needed
3. Ensure state is sent before login packet, or increase wait time

### Issue: Version still not matching
**Causes:**
- Filename doesn't follow expected pattern
- Version extraction is removing too much/too little

**Fix:**
1. Check filename format matches ATCU_X.X.X_RELMM.bin pattern
2. Review extractVersionFromFilename() logic
3. Add debug logging to see what's being extracted

### Issue: Wrong next version selected
**Causes:**
- Firmware sequence in servers.json is incorrect
- Multiple entries have same extracted version

**Fix:**
1. Verify servers.json firmware array is in correct upgrade sequence
2. Ensure each firmware entry has a unique version
3. Check for duplicate entries

---

## Files to Monitor

| File | What It Shows | When to Check |
|------|---------------|---------------|
| `results/login_packets.json` | All captured device logins with state & version | After each device login |
| Application Logs | Detailed messages about state/version processing | During troubleshooting |
| `config.properties` | Configuration (states, default values) | If state mapping needed |
| `input/servers.json` | Firmware sequences and filenames | Before running FOTA |

---

## Verification Checklist

- [ ] Code compiles without errors: `mvn clean compile`
- [ ] Tests pass: `mvn test`
- [ ] Device state captured in logs: `[SR] Captured device state:`
- [ ] Version extracted from filename: `[RESOLVER] File: ... Binary Version:`
- [ ] Version matching succeeds: `[RESOLVER] Current version matched`
- [ ] Login packet JSON shows correct state (not "Default")
- [ ] Login packet JSON shows correct version (matches device)
- [ ] Next firmware version correctly selected from sequence
- [ ] FOTA batch generated with correct version
- [ ] No error messages in application logs

---

## Next Steps

1. **Compile and Run**: Execute `mvn clean install` to build the updated code
2. **Test with Device**: Connect device and verify state capture
3. **Monitor Logs**: Watch for the new debug messages listed above
4. **Verify Results**: Check login_packets.json for correct state and version
5. **Test FOTA Flow**: Run complete FOTA cycle and verify correct firmwares are selected

If you encounter any issues, check the troubleshooting section above or review the detailed changes in DETAILED_CHANGES.md.
