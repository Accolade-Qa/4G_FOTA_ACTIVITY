package com.aepl.atcu;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Entry point for the FOTA (Firmware Over-The-Air) Automation tool.
 * Configures hard-coded parameters and orchestrates the FOTA automation process.
 */
public class Launcher {
	private static final Logger logger = LogManager.getLogger(Launcher.class);

	// Hard-coded configuration values
	// Keep blank/null to auto-detect active serial port at startup.
	private static final String SERIAL_PORT = "";
	private static final int BAUD_RATE = 115200;

	private static final String FIRMWARE_JSON = "input/servers.json";
	private static final String AUDIT_CSV = "results/fota_audit.csv";
	private static final String LOGIN_JSON = "results/login_packets.json";

	private static final String PORTAL_URL = "http://aepl-tcu4g-qa.accoladeelectronics.com:6102/login";
	private static final String PORTAL_USER = "suraj.bhalerao@accoladeelectronics.com";
	private static final String PORTAL_PASS = "79hqelye";

	private static final String DEFAULT_STATE = "Default";

	public static void main(String[] args) {
		setupDirectories();

		try {
			logger.info("===== FOTA AUTOMATION LAUNCHER =====");
			logger.info("Serial Port: {}",
					(SERIAL_PORT == null || SERIAL_PORT.trim().isEmpty()) ? "AUTO-DETECT" : SERIAL_PORT);
			logger.info("Baud Rate: {}", BAUD_RATE);
			logger.info("Firmware JSON: {}", FIRMWARE_JSON);
			logger.info("Audit CSV: {}", AUDIT_CSV);
			logger.info("Portal URL: {}", PORTAL_URL);
			logger.info("Default State: {}", DEFAULT_STATE);

			Orchestrator orch = new Orchestrator(SERIAL_PORT, BAUD_RATE, AUDIT_CSV, FIRMWARE_JSON,
					DEFAULT_STATE, LOGIN_JSON);
			orch.start(PORTAL_URL, PORTAL_USER, PORTAL_PASS);
		} catch (Exception e) {
			logger.fatal("Fatal error starting orchestrator: {}", e.getMessage(), e);
			System.err.println("FATAL: " + e.getMessage());
			e.printStackTrace();
			System.exit(1);
		}
	}

	/**
	 * Ensures required directories exist.
	 */
	private static void setupDirectories() {
		String[] dirs = { "input", "output", "logs", "results", "screenshots" };
		for (String dir : dirs) {
			Path path = Paths.get(dir);
			if (Files.notExists(path)) {
				try {
					Files.createDirectory(path);
					logger.info("Created directory: {}", dir);
				} catch (Exception e) {
					logger.warn("Failed to create directory {}: {}", dir, e.getMessage());
				}
			}
		}
	}
}
