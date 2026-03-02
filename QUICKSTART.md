# QUICK START GUIDE - Simplified FOTA Automation

## 1️⃣ Configure Your Setup

### Edit `config.properties`
```properties
# Must set:
serial.port=COM3                    # Your device serial port
login.user=your@email.com          # Web portal username
login.pass=yourpassword            # Web portal password

# Optional (defaults shown):
serial.baud=115200
login.url=http://aepl-tcu4g-qa.accoladeelectronics.com:6102/login
firmware.json=input/servers.json
audit.csv=results/fota_audit.csv
state=Default
```

---

## 2️⃣ Prepare Input Files

### `input/servers.json` - Version Mapping
```json
[
  {
    "state": "Maharashtra",
    "firmware": [
      { "firmwareVersion": "5.2.12", "fileName": "ATCU_5.2.8_REL18.bin" },
      { "firmwareVersion": "5.2.15", "fileName": "ATCU_5.2.9_REL07.bin" },
      { "firmwareVersion": "5.2.18", "fileName": "ATCU_5.2.9_REL05.bin" }
    ]
  },
  {
    "state": "Bihar",
    "firmware": [
      { "firmwareVersion": "5.2.11", "fileName": "ATCU_5.2.8_REL24.bin" },
      { "firmwareVersion": "5.2.12", "fileName": "ATCU_5.2.9_REL04.bin" }
    ]
  }
]
```

### `input/fota_batch.csv` (Optional)
```csv
UIN,UFW,MODEL,STATE,IMEI
ACON4NA082300092233,5.2.1,4G,Maharashtra,861564061380138
```

---

## 3️⃣ Run the Application

### Compile
```bash
cd d:\AEPL_AUTOMATION\FOTA_ACTIVITY
mvn clean compile
```

### Execute
```bash
mvn exec:java -Dexec.mainClass="com.aepl.atcu.Launcher"
```

Or directly:
```bash
java -cp target/classes:lib/* com.aepl.atcu.Launcher
```

---

## 4️⃣ Monitor Progress

### Console Output
```
===== FOTA AUTOMATION START =====
--- Starting New Device Upgrade Cycle ---
STEP 1-3: Waiting for login packet from device (timeout: 180s)...
STEP 4: Login packet received and stored
Device Info - UIN: ACON4NA082300092233, IMEI: 861564061380138, ...
STEP 5-6: Checking if device needs upgrade...
Next version to install: 5.2.15
STEP 7: Preparing FOTA batch...
STEP 8: Firing FOTA batch to web endpoint...
STEP 9-10: Monitoring device for download completion...
Download reached 100%. Device is rebooting...
STEP 11: Waiting for post-reboot login packet...
VERIFIED: Device rebooted successfully. New version: 5.2.15
```

### Output Files
- ✅ **logs/** → Serial communication logs (per device IMEI)
- ✅ **output/** → Generated batch CSVs
- ✅ **results/fota_audit.csv** → Final report
- ✅ **screenshots/** → Web portal screenshots

---

## 5️⃣ Understand the 12-Step Flow

```
1️⃣-3️⃣  Device sends login packet (IMEI, UIN, VIN, ICCID, version)
   ↓
4️⃣  Store login packet data
   ↓
5️⃣-6️⃣  Compare device version with servers.json
   ├─ If up-to-date → Mark DONE & EXIT
   └─ If older → Get next version
   ↓
7️⃣  Create batch CSV with device info
   ↓
8️⃣  Upload batch to web portal
   ↓
9️⃣  Monitor serial for download starting
   ↓
🔟  Wait for download to reach 100%
   → Device reboots automatically
   ↓
1️⃣1️⃣  Verify new version in post-reboot login packet
   ├─ Match → Mark SUCCESS
   └─ No match → Mark FAILED
   ↓
1️⃣2️⃣  Repeat for next version OR mark device DONE
```

---

## 6️⃣ Troubleshooting

### **Serial Port Not Found**
```
ERROR: Failed to open port. Tried: COM1, COM2, COM3...
```
**Solution:** 
- Check device is plugged in
- Verify port in Device Manager or `mode COM?`
- Update `config.properties` with correct port

### **Login Packet Not Received**
```
Failed to get login packet. Retrying cycle...
```
**Solution:**
- Ensure device is powered and connected
- Check serial logs: `logs/` folder
- Verify baud rate matches device (usually 115200)
- Wait 30+ seconds, device may need startup time

### **Version Not Found in JSON**
```
No upgrade needed or State 'Default' mapping missing...
```
**Solution:**
- Check device state in login packet (e.g., "Maharashtra")
- Verify `servers.json` has that state defined
- Or set `state=Maharashtra` in config.properties

### **Web Portal Authentication Failed**
```
Login verification failed.
```
**Solution:**
- Verify credentials in `config.properties`
- Check portal URL is accessible
- Ensure user account has permission to create batches

### **Download Not Reaching 100%**
```
Download monitoring timeout. Progress did not reach 100%
```
**Solution:**
- Check device is still connected
- Verify web portal batch was created successfully
- Check device has sufficient storage
- Look at device serial logs in `logs/` folder

### **Version Verification Failed After Reboot**
```
Version verification failed. Expected: 5.2.15, Got: 5.2.1
```
**Solution:**
- Device may not have completed restart
- Increase wait time (modify code: `Thread.sleep(20000)` → `30000`)
- Check device logs for upgrade errors
- Ensure batch file had correct target version

---

## 7️⃣ Audit Report Format

Every upgrade is logged to `results/fota_audit.csv`:

```csv
UIN,FROMVERSION,TOVERSION,STATUS,DETAILS
ACON4NA082300092233,5.2.1,5.2.12,SUCCESS,Device rebooted and upgrade verified
ACON4NA082300092234,5.2.1,5.2.10,FAILED,Download monitoring timeout
ACON4NA082300092235,5.2.15,5.2.15,COMPLETED,Device up-to-date. All versions installed.
```

**Status Types:**
- `SUCCESS` → Device upgraded and verified ✅
- `FAILED` → Upgrade did not complete  ❌
- `COMPLETED` → Device already on latest version ✅

---

## 8️⃣ What's Different (Simplified)

### ❌ Removed Complexity
- No more parallel async execution
- No more artificial state maps
- No more dual monitoring (Serial + Web)
- No more fallback chains

### ✅ New Simplicity
- Linear 12-step flow
- Direct serial communication focus
- Clear version comparison logic
- Step-by-step logging for easy debugging

---

## 9️⃣ Example Execution Output

```
===== FOTA AUTOMATION START =====
2026-02-27 17:30:00 INFO Loaded config from: d:\...\config.properties
2026-02-27 17:30:02 INFO Opened COM3
2026-02-27 17:30:05 INFO Login successful

--- Starting New Device Upgrade Cycle ---
2026-02-27 17:30:10 INFO STEP 1-3: Waiting for login packet...
2026-02-27 17:30:45 INFO STEP 4: Login packet received and stored
2026-02-27 17:30:45 INFO Device Info - UIN: ACON4NA082300092233, IMEI: 861564061380138
2026-02-27 17:30:45 INFO STEP 5-6: Checking if device needs upgrade...
2026-02-27 17:30:46 INFO Next version to install: 5.2.15
2026-02-27 17:30:47 INFO STEP 7: Preparing FOTA batch...
2026-02-27 17:30:48 INFO Batch file prepared: output\fota_batch_20260227_173048.csv
2026-02-27 17:30:49 INFO STEP 8: Firing FOTA batch to web endpoint...
2026-02-27 17:30:55 INFO Web batch creation result: true
2026-02-27 17:30:56 INFO STEP 9-10: Monitoring device for download completion...
2026-02-27 17:31:05 INFO Download progress: 25%
2026-02-27 17:31:15 INFO Download progress: 50%
2026-02-27 17:31:25 INFO Download progress: 75%
2026-02-27 17:31:35 INFO Download reached 100%. Device is rebooting...
2026-02-27 17:31:55 INFO STEP 11: Waiting for post-reboot login packet...
2026-02-27 17:32:10 INFO VERIFIED: Device rebooted successfully. New version: 5.2.15
2026-02-27 17:32:10 INFO FOTA upgrade successful to version: 5.2.15
2026-02-27 17:32:10 INFO Waiting before next cycle...

--- Starting New Device Upgrade Cycle ---
(process repeats for next version...)

[Later, when no more versions available]
2026-02-27 17:45:00 INFO STEP 12: No more versions available. Device is up-to-date.
2026-02-27 17:45:00 INFO Device ACON4NA082300092233 marked as DONE
===== FOTA AUTOMATION COMPLETE =====
```

---

## 🔟 Performance Expectations

| Operation | Time |
|-----------|------|
| Serial connect | 2-5 sec |
| Web login | 3-8 sec |
| Wait for login packet | 10-60 sec |
| Firmware comparison | <1 sec |
| Batch creation | 2-5 sec |
| Download (typical) | 3-10 min |
| Device reboot | 10-20 sec |
| Version verification | 5-15 sec |
| **Total per upgrade** | **15-45 min** |

---

## ✅ You're Ready!

1. ✅ Edit `config.properties`
2. ✅ Create `input/servers.json`
3. ✅ Run the tool
4. ✅ Monitor logs
5. ✅ Check `results/fota_audit.csv`

That's it! The simplified automated FOTA workflow is ready. 🚀
