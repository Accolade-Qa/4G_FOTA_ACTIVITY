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
    private final String auditCsvPath;
    private final FirmwareResolver resolver;
    private final String defaultState;
    private final String loginJsonPath; // file where we persist observed login packets

	/**
	 * Validates if the UIN starts with the required prefix (ACON).
	 * 
	 * @param uin The UIN to validate
	 * @return True if UIN starts with ACON, false otherwise
	 */
	private static boolean isValidUin(String uin) {
		return uin != null && uin.startsWith(UIN_PREFIX);
	}

	/**
	 * Validates if the IMEI is in valid format (13-15 digits).
	 * 
	 * @param imei The IMEI to validate
	 * @return True if IMEI is valid, false otherwise
	 */
	private static boolean isValidImei(String imei) {
		return imei != null && !imei.isEmpty() && IMEI_PATTERN.matcher(imei).matches();
	}

	/**
	 * Constructs the Orchestrator with required configuration paths.
	 * 
	 * @param serialPort       The COM port for device serial communication
	 * @param baud             The baud rate for serial communication
	 * @param auditCsvPath     Path where audit reports are stored
	 * @param firmwareJsonPath Path to the JSON file containing version mappings
	 * @param defaultState     The fallback state to use if device reports 'Default'
     * @param loginJsonPath    Location where observed login packets will be saved
     * @throws Exception If initialization of serial components fails
     */
    /**
     * Primary constructor used by production code.  Creates its own
     * {@link SerialReader} instance.
     */
    public Orchestrator(String serialPort, int baud, String auditCsvPath, String firmwareJsonPath, 
            String defaultState, String loginJsonPath) throws Exception {
        this(new SerialReader(serialPort, baud), auditCsvPath, firmwareJsonPath, defaultState, loginJsonPath);
    }

    /**
     * Package-private constructor allowing a custom reader (e.g. stub) for tests.
     */
    Orchestrator(SerialReader serialReader, String auditCsvPath, String firmwareJsonPath, 
            String defaultState, String loginJsonPath) throws Exception {
        this.serialReader = serialReader;
        this.auditCsvPath = auditCsvPath;
        this.resolver = new FirmwareResolver(firmwareJsonPath);
        // provide resolver to serial reader so it can map state abbrev during parsing
        this.serialReader.setStateResolver(this.resolver);
        this.defaultState = defaultState;
        this.loginJsonPath = (loginJsonPath == null || loginJsonPath.isEmpty()) ? "results/login_packets.json" : loginJsonPath;
    }

	/**
	 * Starts the simplified FOTA automation loop.
	 * 
	 * @param loginUrl URL for the FOTA web portal
	 * @param user     Username for web portal authentication
	 * @param pass     Password for web portal authentication
	 * @throws Exception If a fatal error occurs during orchestration
	 */
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
				LoginPacketInfo loginInfo = waitForLoginPacket(180);

                if (loginInfo == null) {
                    logger.error("Failed to get login packet within timeout. restarting cycle and waiting for new packet...");
                    serialReader.resetState();
                    serialReader.sendCommand("*SET#CRST#1#");
                    continue;
                }

                // Validate UIN starts with ACON
                if (!isValidUin(loginInfo.uin)) {
                    logger.error("Invalid UIN received (must start with {}): {}. Rejecting device.",
                            UIN_PREFIX, loginInfo.uin);
                    serialReader.resetState();
                    serialReader.sendCommand("*SET#CRST#1#");
                    continue;
                }
                // Validate IMEI is in proper format (13-15 digits)
                if (!isValidImei(loginInfo.imei)) {
                    logger.error("Invalid IMEI received (must be 13-15 digits): {}. Rejecting device.",
                            loginInfo.imei);
                    serialReader.resetState();
                    serialReader.sendCommand("*SET#CRST#1#");
                    continue;
                }

                // STEP 4: Store login packet info
                logger.info("STEP 4: Login packet received and stored");
                LoginPacketStore.persist(loginJsonPath, loginInfo);

                String currentVer = loginInfo.version;
                // interpret state abbreviation if necessary
                String deviceState = loginInfo.state;
                if (deviceState != null && resolver != null) {
                    try {
                        String mapped = resolver.resolveStateName(deviceState);
                        if (mapped != null) {
                            deviceState = mapped;
                            logger.info("[ORCH] Mapped state abbreviation '{}' to '{}'", loginInfo.state, deviceState);
                        }
                    } catch (Exception e) {
                        logger.warn("[ORCH] Error mapping state '{}': {}", deviceState, e.getMessage());
                    }
                }
                if (deviceState == null || "Default".equalsIgnoreCase(deviceState)) {
                    deviceState = defaultState;
                }

                logger.info("Device Info - UIN: {}, IMEI: {}, VIN: {}, ICCID: {}, State: {}, Current Version: {}",
                        loginInfo.uin, loginInfo.imei, loginInfo.vin, loginInfo.iccid, deviceState, currentVer);

                // STEP 5: Validate that the device's current version exists in the servers.json
                // for the reported state (critical check before preparing FOTA batch)
                logger.info("STEP 5: Validating device version against state configuration...");
                try {
                    boolean versionExists = resolver.validateVersionExists(deviceState, currentVer);
                    if (!versionExists) {
                        logger.error("[VALIDATION FAILED] Device version '{}' is NOT found in servers.json for state '{}'. " +
                                "Cannot proceed with FOTA batch preparation. Rejecting device.", currentVer, deviceState);
                        FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, currentVer,
                                "REJECTED", "Version not found in servers.json for state: " + deviceState);
                        logger.info("Device {} rejected due to version mismatch", loginInfo.uin);
                        serialReader.resetState();
                        serialReader.sendCommand("*SET#CRST#1#");
                        continue;
                    }
                    logger.info("Version validation PASSED - Device version '{}' is valid for state '{}'", currentVer, deviceState);
                } catch (Exception e) {
                    logger.error("[VALIDATION ERROR] Exception during version validation: {}", e.getMessage(), e);
                    FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, currentVer,
                            "ERROR", "Version validation error: " + e.getMessage());
                    serialReader.resetState();
                    serialReader.sendCommand("*SET#CRST#1#");
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
                String outputPath = java.nio.file.Paths.get("output").resolve(outputFileName).toAbsolutePath().toString();

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
                    logger.error("STEP 8 failed: batch was not created on portal. Skipping download monitoring for this cycle.");
                    FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, nextVersion,
                            "FAILED", "Web batch creation failed");
                    Thread.sleep(1000);
                    continue;
                }

                // STEP 9-10: Monitor for downloading completion
                logger.info("STEP 9-10: Monitoring device for download completion...");
                boolean downloadComplete = monitorDownloadProgress(batchName, nextVersion);

                if (!downloadComplete) {
                    logger.error("Download did not complete successfully");
                    FotaFileGenerator.writeAuditReport(auditCsvPath, loginInfo.uin, currentVer, nextVersion,
                            "FAILED", "Download monitoring timeout or incomplete");
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

    /**
     * Waits for a complete login packet from the device.
     * @param timeoutSeconds Maximum time to wait in seconds
     * @return LoginPacketInfo if received, null otherwise
     */
    /*
     * Package-private so tests may override behaviour.
     */
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

    /**
     * Monitors serial output for download completion (100%).
     * STEP 9: Observe logs for downloading progress
     * STEP 10: When downloading reaches 100%, device reboots once
     *
     * @param batchName Name of the batch being monitored
     * @param targetVersion Expected version after upgrade
     * @return True if download completed and version verified, false otherwise
     */
    /*
     * Package-private so tests may exercise the complex post-download login
     * logic.  This method now tolerates multiple reboot/login cycles until the
     * device actually reports the desired targetVersion.
     */
    boolean monitorDownloadProgress(String batchName, String targetVersion) throws InterruptedException {
        int maxIterations = 1800; // allow up to 30 minutes at 1s granularity
        double lastProgress = -1;
        int stagnantCount = 0;
        final int MAX_STAGNANT = 120; // 2 minutes stuck

        for (int i = 0; i < maxIterations; i++) {
            double progress = serialReader.getLastDownloadProgress();

            if (progress == lastProgress) {
                stagnantCount++;
            } else {
                stagnantCount = 0;
            }

            if (stagnantCount >= MAX_STAGNANT) {
                logger.error("Download progress stuck at {}% for {} seconds", progress, stagnantCount);
                return false;
            }

            lastProgress = progress;

            int progressInt = (int) progress;
            if (progressInt > 0 && progressInt % 50 == 0 && i % 50 == 0) {
                logger.info("Download progress: {}%", progressInt);
            }

            if (progress >= 100.0) {
                logger.info("Download reached 100%. Waiting for reboot and final login sequence...");
                serialReader.resetState();

                // after download completes the device will reboot several times as
                // it applies the update; each reboot generates a login packet but
                // the version field may not reflect the final target until the
                // last reboot.  We therefore loop, collecting packets until we see
                // the expected version or we hit an overall timeout.
                long overallStart = System.currentTimeMillis();
                final long overallTimeoutMs = 120 * 1000L; // 2 minutes
                while ((System.currentTimeMillis() - overallStart) < overallTimeoutMs) {
                    LoginPacketInfo newLogin = waitForLoginPacket(30);
                    if (newLogin != null) {
                        LoginPacketStore.persist(loginJsonPath, newLogin);
                        if (targetVersion.equals(newLogin.version)) {
                            logger.info("VERIFIED: Device rebooted successfully. New version: {}", newLogin.version);
                            return true;
                        } else {
                            logger.info("Intermediate login packet version {} received, expecting {}. Waiting for next reboot...",
                                    newLogin.version, targetVersion);
                            // clear stored packet and keep waiting
                            serialReader.resetState();
                            continue;
                        }
                    }
                    // if waitForLoginPacket returned null, just loop until overall
                    // timeout elapses
                }
                logger.error("Timeout waiting for login packet with target version {}", targetVersion);
                return false;
            }

            Thread.sleep(1000);
        }

        return false;
    }

	/**
	 * Performs a graceful shutdown of all orchestrated components.
	 */
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
