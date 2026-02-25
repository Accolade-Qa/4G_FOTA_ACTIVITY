package com.aepl.atcu;

import com.aepl.atcu.logic.FirmwareResolver;
import com.aepl.atcu.web.FotaWebClient;
import com.aepl.atcu.util.FotaFileGenerator;
import com.aepl.atcu.util.LoginPacketInfo;

import java.nio.file.Paths;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * High-level workflow manager for the FOTA process.
 * The Orchestrator coordinates between serial communication, web automation,
 * and version resolution logic to automate continuous device upgrades.
 * 
 * NOTE: The workflow follows these primary steps:
 * 1. Initialize Serial and Web components.
 * 2. Continuously monitor serial data for device status/versions.
 * 3. Resolve target versions using a JSON mapping.
 * 4. Create and monitor FOTA batches on the web portal.
 * 5. Verify successful upgrades via both Serial and Web feedback.
 */
public class Orchestrator {

	private static final Logger logger = LogManager.getLogger(Orchestrator.class);
	private final SerialReader serialReader;
	private FotaWebClient webClient;
	private final String chromeDriverPath;
	private final String firmwareCsvPath;
	private final String auditCsvPath;
	private final FirmwareResolver resolver;
	private final String defaultState;

	/**
	 * Constructs the Orchestrator with required configuration paths and connection
	 * details.
	 * 
	 * @param serialPort       The COM port for device serial communication
	 * @param baud             The baud rate for serial communication
	 * @param chromeDriverPath Path to the ChromeDriver executable
	 * @param firmwareCsvPath  Path to the source CSV for batch generation
	 * @param auditCsvPath     Path where audit reports are stored
	 * @param firmwareJsonPath Path to the JSON file containing version mappings
	 * @param defaultState     The fallback state to use if device reports 'Default'
	 * @throws Exception If initialization of serial or web components fails
	 */
	public Orchestrator(String serialPort, int baud, String chromeDriverPath, String firmwareCsvPath,
			String auditCsvPath, String firmwareJsonPath, String defaultState) throws Exception {
		this.serialReader = new SerialReader(serialPort, baud);
		this.chromeDriverPath = chromeDriverPath;
		this.firmwareCsvPath = firmwareCsvPath;
		this.auditCsvPath = auditCsvPath;
		this.resolver = new FirmwareResolver(firmwareJsonPath);
		this.defaultState = defaultState;
	}

	/**
	 * Starts the continuous FOTA automation loop.
	 * 
	 * @param loginUrl URL for the FOTA web portal login
	 * @param user     Username for web portal authentication
	 * @param pass     Password for web portal authentication
	 * @param deviceId The ID of the device being monitored (used for logging
	 *                 fallback)
	 * @throws Exception If a fatal error occurs during the orchestration process
	 */
	public void start(String loginUrl, String user, String pass, String deviceId) throws Exception {
		try {
			serialReader.start();
			this.webClient = new FotaWebClient(chromeDriverPath);
			webClient.login(loginUrl, user, pass);

			while (true) {
				logger.info("--- Starting New FOTA Cycle ---");
				serialReader.resetState();

				logger.info("Waiting for aeplFwVer line (120s timeout)...");
				long startWait = System.currentTimeMillis();
				while (!serialReader.isAeplFwVerFound() && (System.currentTimeMillis() - startWait) < 120000) {
					Thread.sleep(1000);
					if ((System.currentTimeMillis() - startWait) % 10000 < 1000) {
						logger.info("[ORC] Still waiting for aeplFwVer. LoginPacket received: {}",
								(serialReader.getLastLoginPacketInfo() != null));
					}
				}

				LoginPacketInfo loginInfo = serialReader.getLastLoginPacketInfo();
				String currentVer = serialReader.getLastAeplFwVersion();
				boolean usingAeplFwVer = serialReader.isAeplFwVerFound();

				if (!usingAeplFwVer) {
					if (loginInfo != null && loginInfo.version != null && !loginInfo.version.trim().isEmpty()) {
						currentVer = loginInfo.version.trim();
						logger.warn(
								"aeplFwVer not found after timeout. Falling back to version from LoginPacket: {}",
								currentVer);
					} else {
						logger.error("aeplFwVer not found after timeout and LoginPacket version unavailable. Retrying cycle...");
						continue;
					}
				}

				if (currentVer == null || currentVer.trim().isEmpty()) {
					logger.error("Current version is empty after parsing/fallback. Retrying cycle...");
					continue;
				}

				logger.info("Current Device Version (source: {}): {}", usingAeplFwVer ? "aeplFwVer" : "LoginPacket",
						currentVer);

				if (loginInfo != null && (loginInfo.uin == null || loginInfo.uin.trim().isEmpty())) {
					logger.error("Device UIN from LoginPacket is empty. Cannot proceed with FOTA. Retrying cycle...");
					continue;
				}

				// Use login packet state if it's not "Default", otherwise use config
				// defaultState
				String state = (loginInfo != null && !"Default".equalsIgnoreCase(loginInfo.state))
						? loginInfo.state
						: defaultState;

				String targetUfw = resolver.resolveNextVersion(state, currentVer);

				if (targetUfw == null) {
					logger.info(
							"No upgrade needed or State '{}' mapping missing in JSON for version '{}'. Waiting for next cycle...",
							state, currentVer);
					Thread.sleep(30000);
					continue;
				}

				logger.info("Next Target UFW from JSON: " + targetUfw + " (State: " + state + ")");

				String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
				String outputFileName = "fota_batch_" + timestamp + ".csv";
				String outputPath = Paths.get("output").resolve(outputFileName).toAbsolutePath().toString();

				logger.info("Generating batch file: " + outputPath);
				String localizedFilePath;

				if (loginInfo != null && loginInfo.uin != null && !loginInfo.uin.trim().isEmpty()) {
					logger.info("[ORC] Constructing batch record from Login Packet for UIN: {} with State: {}",
							loginInfo.uin, state);
					LoginPacketInfo nextInfo = new LoginPacketInfo(loginInfo.imei, loginInfo.iccid, loginInfo.uin,
							targetUfw, loginInfo.vin, loginInfo.model, state);
					List<LoginPacketInfo> list = new ArrayList<>();
					list.add(nextInfo);
					localizedFilePath = FotaFileGenerator.writeLoginPacketInfoCsv(list, outputPath);
				} else {
					logger.info(
							"[ORC] No valid login packet found, but version is known. Using source CSV '{}' for batch generation with target version '{}'",
							firmwareCsvPath, targetUfw);
					localizedFilePath = FotaFileGenerator.generateBatchFileWithExplicitVersion(firmwareCsvPath,
							outputPath, targetUfw);
				}

				String batchName = "AutoFota_" + timestamp;
				logger.info("Starting Web Automation for Batch: " + batchName);

				CompletableFuture<Boolean> webTask = CompletableFuture.supplyAsync(() -> {
					try {
						return webClient.createBatch(batchName, "Automated Continuous FOTA " + timestamp,
								localizedFilePath);
					} catch (Exception e) {
						logger.error("Web Client Error: " + e.getMessage());
						return false;
					}
				});

				boolean serialCompleted = monitorProgress(batchName, targetUfw);

				boolean webCompleted = false;
				try {
					webCompleted = webTask.get(10, TimeUnit.MINUTES);
				} catch (Exception e) {
					logger.error("Web task did not finish or failed: " + e.getMessage());
				}

				if (serialCompleted && webCompleted) {
					logger.info("FOTA SUCCESS: Both Serial and Web confirmed upgrade to " + targetUfw);
					FotaFileGenerator.writeAuditReport(auditCsvPath, (loginInfo != null ? loginInfo.uin : "CSV_BATCH"),
							currentVer, targetUfw, "SUCCESS", "Dual monitoring verified completion.");
				} else {
					String details = String.format("Serial:%s, Web:%s", serialCompleted, webCompleted);
					logger.error("FOTA FAILURE: " + details);
					FotaFileGenerator.writeAuditReport(auditCsvPath, (loginInfo != null ? loginInfo.uin : "CSV_BATCH"),
							currentVer, targetUfw, "FAILURE", details);
					logger.info("Stopping continuous loop due to failure.");
					break;
				}

				logger.info("Waiting for device to settle before next upgrade...");
				Thread.sleep(20000);
			}
		} finally {
			shutdown();
			logger.info("Graceful shutdown complete.");
		}
	}

	/**
	 * Monitors device serial output for firmware download progress.
	 * 
	 * @param batchName Name of the current FOTA batch
	 * @param targetVer The expected version after upgrade
	 * @return True if download completes and version is verified over serial, false
	 *         otherwise
	 * @throws InterruptedException If the monitoring thread is interrupted
	 */
	private boolean monitorProgress(String batchName, String targetVer) throws InterruptedException {
		for (int i = 0; i < 180; i++) {
			double progress = serialReader.getLastDownloadProgress();
			logger.info("Terminal Progress for " + batchName + ": " + String.format("%.2f", progress) + "%");

			if (progress >= 100.0) {
				logger.info("Download complete via Serial. Waiting for reboot and verification...");
				Thread.sleep(20000);
				String finalVer = serialReader.getLastSoftwareVersion();
				if (targetVer.equals(finalVer)) {
					logger.info("VERIFIED via Serial: Device is now on " + finalVer);
					return true;
				} else {
					logger.warn("Serial verification failed. Expected " + targetVer + " but found " + finalVer);
				}
			}

			Thread.sleep(10000);
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
