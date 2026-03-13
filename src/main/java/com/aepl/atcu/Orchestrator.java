package com.aepl.atcu;

import com.aepl.atcu.logic.FirmwareResolver;
import com.aepl.atcu.web.FotaWebClient;
import com.aepl.atcu.util.FotaFileGenerator;
import com.aepl.atcu.util.LoginPacketInfo;
import com.aepl.atcu.util.LoginPacketStore;

import java.util.ArrayList;
import java.util.List;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Simplified FOTA Orchestrator following a direct workflow:
 * 1. Start reading logs from serial port
 * 2. Fire OTA command (device reboots, generates login packet)
 * 3. Observe login packet (extract device info: IMEI, VIN, UIN, ICCID, version)
 * 4. Store login packet for future use
 * 5. Compare device version with JSON (state + versions)
 * 6. If device version is older, take next version
 * 7. Prepare FOTA batch payload
 * 8. Fire to endpoint (web)
 * 9. Monitor logs for OTA request/response, downloading
 * 10. If downloading reaches 100%, device reboots once
 * 11. Observe next login packet, store it, repeat until no more versions
 * 12. Mark device as done, write audit file
 */
public class Orchestrator {

    private static final Logger logger = LogManager.getLogger(Orchestrator.class);
    private static final String UIN_PREFIX = "ACON";
    private static final java.util.regex.Pattern IMEI_PATTERN = java.util.regex.Pattern.compile("^\\d{13,15}$");
    private final SerialReader serialReader;
    private FotaWebClient webClient;
    private final FirmwareResolver resolver;
    private final String auditCsvPath;
    private final String loginJsonPath;

    private static boolean isValidUin(String uin) {
        return uin != null && uin.startsWith(UIN_PREFIX);
    }

    private static boolean isValidImei(String imei) {
        return imei != null && !imei.isEmpty() && IMEI_PATTERN.matcher(imei).matches();
    }

    public Orchestrator(String serialPort, int baud, String auditCsvPath, String firmwareJsonPath,
            String loginJsonPath) throws Exception {
        this(new SerialReader(serialPort, baud), auditCsvPath, firmwareJsonPath, loginJsonPath);
    }

    Orchestrator(SerialReader serialReader, String auditCsvPath, String firmwareJsonPath,
            String loginJsonPath) throws Exception {
        this.serialReader = serialReader;
        this.auditCsvPath = auditCsvPath;
        this.resolver = new FirmwareResolver(firmwareJsonPath);
        this.loginJsonPath = (loginJsonPath == null || loginJsonPath.isEmpty()) ? "results/login_packets.json"
                : loginJsonPath;
    }

    public void start(String loginUrl, String user, String pass) throws Exception {
        try {
            // Step 1: Initialize serial communication
            logger.info("===== FOTA AUTOMATION START =====");
            serialReader.start();

            // Step 2..12: Main FOTA cycle
            while (true) {
                logger.info("\n--- Starting New Device Upgrade Cycle ---");
                serialReader.resetState();

                // STEP 1-3: Read serial logs, fire OTA command, observe login packet
                logger.info("STEP 1-3: Waiting for login packet from device (timeout: 180s)...");
                // serialReader.sendCommand("*SET#CRST#1#");
                LoginPacketInfo loginInfo = waitForLoginPacket(180);

                if (loginInfo == null) {
                    logger.error(
                            "Failed to get login packet within timeout. restarting cycle and waiting for new packet...");
                    serialReader.resetState();
                    // serialReader.sendCommand("*SET#CRST#1#");
                    continue;
                }

                // Validate UIN starts with ACON
                if (!isValidUin(loginInfo.uin)) {
                    rejectDevice(loginInfo, "Invalid UIN (must start with " + UIN_PREFIX + "): " + loginInfo.uin);
                    continue;
                }
                // Validate IMEI is in proper format (13-15 digits)
                if (!isValidImei(loginInfo.imei)) {
                    rejectDevice(loginInfo, "Invalid IMEI (must be 13-15 digits): " + loginInfo.imei);
                    continue;
                }

                // STEP 4: Store login packet info
                logger.info("STEP 4: Login packet received and stored");
                LoginPacketStore.persist(loginJsonPath, loginInfo);

                String currentVer = loginInfo.version;
                // Determine device state (use default if not provided)
                String deviceState = loginInfo.state;
                if (deviceState == null || deviceState.trim().isEmpty() || "Default".equalsIgnoreCase(deviceState)) {
                    deviceState = Launcher.getDefaultState();
                }

                logger.info("Device Info - UIN: {}, IMEI: {}, VIN: {}, ICCID: {}, State: {}, Current Version: {}",
                        loginInfo.uin, loginInfo.imei, loginInfo.vin, loginInfo.iccid, deviceState, currentVer);

                // STEP 5: Validate that the device's current version exists in the servers.json
                // for the reported state (critical check before preparing FOTA batch)
                logger.info("STEP 5: Validating device version against state configuration...");
                try {
                    boolean versionExists = resolver.validateVersionExists(deviceState, currentVer);
                    if (!versionExists) {
                        logger.error(
                                "[VALIDATION FAILED] Device version '{}' is NOT found in servers.json for state '{}'. "
                                        +
                                        "Cannot proceed with FOTA batch preparation. Rejecting device.",
                                currentVer, deviceState);
                        FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, currentVer,
                                "REJECTED", "Version not found in servers.json for state: " + deviceState);
                        logger.info("Device {} rejected due to version mismatch", loginInfo.uin);
                        serialReader.resetState();
                        // serialReader.sendCommand("*SET#CRST#1#");
                        continue;
                    }
                    logger.info("Version validation PASSED - Device version '{}' is valid for state '{}'", currentVer,
                            deviceState);
                } catch (Exception e) {
                    handleValidationError(loginInfo, e);
                    continue;
                }

                // STEP 6: Compare version with JSON, get next version
                logger.info("STEP 6: Checking if device needs upgrade...");
                String nextVersion = resolver.resolveNextVersion(deviceState, currentVer);

                if (nextVersion == null) {
                    logger.info("STEP 12: No more versions available. Device is up-to-date.");
                    FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, currentVer,
                            "COMPLETED", "Device up-to-date. All versions installed.");
                    logger.info("Device {} marked as DONE", loginInfo.uin);
                    break;
                }

                logger.info("Next version to install: {}", nextVersion);

                // STEP 7: Prepare FOTA batch payload
                logger.info("STEP 7: Preparing FOTA batch...");
                String timestamp = new java.text.SimpleDateFormat("yyyyMMdd_HHmmss").format(new java.util.Date());
                String outputFileName = "fota_batch_" + timestamp + ".csv";
                String outputPath = java.nio.file.Paths.get("output").resolve(outputFileName).toAbsolutePath()
                        .toString();

                List<LoginPacketInfo> batchList = new ArrayList<>();
                LoginPacketInfo batchInfo = new LoginPacketInfo(loginInfo.imei, loginInfo.iccid, loginInfo.uin,
                        nextVersion, loginInfo.vin, loginInfo.model, deviceState);
                batchList.add(batchInfo);
                String batchFilePath = FotaFileGenerator.writeLoginPacketInfoCsv(batchList, outputPath);

                logger.info("Batch file prepared: {}", batchFilePath);

                // STEP 8: Initialize web client and fire to endpoint
                logger.info("STEP 8: Initializing web client and firing FOTA batch to endpoint...");
                String batchName = "AutoFota_" + timestamp;
                boolean webSuccess = false;
                try {
                    if (this.webClient == null) {
                        this.webClient = new FotaWebClient(null);
                        logger.info("Web client initialized");
                        webClient.login(loginUrl, user, pass);
                        logger.info("Web client logged in successfully");
                    }

                    webSuccess = webClient.createBatch(batchName, "FOTA to version " + nextVersion, batchFilePath);
                    logger.info("Web batch creation result: {}", webSuccess);
                } catch (Exception e) {
                    logger.error("Web client error: {}", e.getMessage());
                    webSuccess = false;
                }

                if (!webSuccess) {
                    handleWebFailure(loginInfo, currentVer, nextVersion);
                    continue;
                }

                // STEP 9-10: Monitor for downloading completion
                logger.info("STEP 9-10: Monitoring device for download completion...");
                serialReader.pauseLoginCapture();
                boolean downloadComplete = monitorDownloadProgress(batchName, nextVersion);

                if (!downloadComplete) {
                    handleDownloadFailure(loginInfo, currentVer, nextVersion);
                } else {
                    logger.info("FOTA upgrade successful to version: {}", nextVersion);
                    FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, nextVersion,
                            "SUCCESS", "Device rebooted and upgrade verified");
                }

                // short pause between cycles
                Thread.sleep(1000);
            }

        } finally {
            shutdown();
            logger.info("===== FOTA AUTOMATION COMPLETE =====");
        }
    }

    LoginPacketInfo waitForLoginPacket(int timeoutSeconds) throws InterruptedException {
        long startTime = System.currentTimeMillis();
        long timeoutMs = timeoutSeconds * 1000L;

        while ((System.currentTimeMillis() - startTime) < timeoutMs) {
            LoginPacketInfo info = serialReader.getLastLoginPacketInfo();
            if (info != null && info.uin != null && !info.uin.trim().isEmpty()
                    && info.version != null && !info.version.trim().isEmpty()) {
                return info;
            }
            // brief sleep to avoid busy loop; small value makes retries fast
            Thread.sleep(250);
        }

        return null;
    }

    boolean monitorDownloadProgress(String batchName, String targetVersion) throws InterruptedException {
        int maxIterations = 1800;
        double lastProgress = -1;
        int stagnantCount = 0;
        final int MAX_STAGNANT = 120;

        for (int i = 0; i < maxIterations; i++) {
            double progress = serialReader.getLastDownloadProgress();

            if (progress == lastProgress) {
                stagnantCount++;
            } else {
                stagnantCount = 0;
            }

            if (stagnantCount >= MAX_STAGNANT) {
                logger.error("Download progress stuck at {}% for {} seconds", progress, stagnantCount);
                serialReader.resumeLoginCapture();
                return false;
            }

            lastProgress = progress;

            int progressInt = (int) progress;
            if (progressInt > 0 && progressInt % 50 == 0 && i % 50 == 0) {
                logger.info("Download progress: {}%", progressInt);
            }

            if (progress >= 100.0) {
                logger.info("Download reached 100%. Waiting for reboot and final login sequence...");
                serialReader.resumeLoginCapture();
                serialReader.resetState();
                long overallStart = System.currentTimeMillis();
                final long overallTimeoutMs = 120 * 1000L;
                while ((System.currentTimeMillis() - overallStart) < overallTimeoutMs) {
                    LoginPacketInfo newLogin = waitForLoginPacket(30);
                    if (newLogin != null) {
                        LoginPacketStore.persist(loginJsonPath, newLogin);
                        if (targetVersion.equals(newLogin.version)) {
                            logger.info("VERIFIED: Device rebooted successfully. New version: {}", newLogin.version);
                            return true;
                        } else {
                            logger.info(
                                    "Intermediate login packet version {} received, expecting {}. Waiting for next reboot...",
                                    newLogin.version, targetVersion);
                            serialReader.resetState();
                            continue;
                        }
                    }
                }
                logger.error("Timeout waiting for login packet with target version {}", targetVersion);
                return false;
            }

            Thread.sleep(1000);
        }

        serialReader.resumeLoginCapture();
        return false;
    }

    /**
     * Rejects a device due to validation failure and prepares for next cycle.
     */
    private void rejectDevice(LoginPacketInfo loginInfo, String reason) throws Exception {
        logger.error("Rejecting device {}: {}", loginInfo.uin, reason);
        FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, loginInfo.version, loginInfo.version,
                "REJECTED", reason);
        serialReader.resetState();
        // serialReader.sendCommand("*SET#CRST#1#");
    }

    /**
     * Handles validation errors during version checking.
     */
    private void handleValidationError(LoginPacketInfo loginInfo, Exception e) throws Exception {
        logger.error("[VALIDATION ERROR] Exception during version validation: {}", e.getMessage(), e);
        FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, loginInfo.version, loginInfo.version,
                "ERROR", "Version validation error: " + e.getMessage());
        serialReader.resetState();
        // serialReader.sendCommand("*SET#CRST#1#");
    }

    /**
     * Handles web batch creation failures.
     */
    private void handleWebFailure(LoginPacketInfo loginInfo, String currentVer, String nextVersion) throws Exception {
        logger.error("Web batch creation failed for device {}", loginInfo.uin);
        FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, nextVersion,
                "FAILED", "Web batch creation failed");
        Thread.sleep(1000);
    }

    /**
     * Handles download monitoring failures.
     */
    private void handleDownloadFailure(LoginPacketInfo loginInfo, String currentVer, String nextVersion) throws Exception {
        logger.error("Download monitoring failed for device {}", loginInfo.uin);
        FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, nextVersion,
                "FAILED", "Download monitoring timeout or incomplete");
    }

    public void shutdown() {
        try {
            if (serialReader != null)
                serialReader.stop();
            if (webClient != null)
                webClient.close();
        } catch (Exception ignored) {
        }
    }
}
