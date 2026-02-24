package com.aepl.atcu;

import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Properties;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Entry point for the FOTA (Firmware Over-The-Air) Automation tool.
 * This class handles configuration loading, environment setup, and orchestrates
 * target tool execution.
 * 
 * NOTE: The tool expects a 'config.properties' file in the execution directory
 * or classpath.
 * It also ensures that the required directory structure (input, output, logs,
 * etc.) is present.
 */
public class Launcher {
	private static final Logger logger = LogManager.getLogger(Launcher.class);
	private static final String CONFIG_FILE = "config.properties";
	public static void main(String[] args) {
		setupDirectories();

		Properties p = new Properties();
		Path cwdConfig = Paths.get(System.getProperty("user.dir")).resolve(CONFIG_FILE);

		try (InputStream in = Files.exists(cwdConfig) ? new FileInputStream(cwdConfig.toFile())
				: Launcher.class.getResourceAsStream("/" + CONFIG_FILE)) {
			if (in != null) {
				p.load(in);
				logger.info("Loaded config from: "
						+ (Files.exists(cwdConfig) ? cwdConfig.toAbsolutePath() : "classpath"));
			} else {
				logger.warn("No config.properties found in working dir or classpath — using defaults or env vars.");
			}
		} catch (Exception e) {
			logger.error("Failed to load config.properties: {}", e.getMessage());
		}

		String serialPort = get(p, "serial.port", "COM22");
		int baud = Integer.parseInt(get(p, "serial.baud", "115200"));
		String chromeDriver = get(p, "chromedriver.path", "D:\\Software\\chromedriver-win64\\chromedriver.exe");

		String firmwareCsv = get(p, "firmware.csv", "input/fota_list.csv");
		String auditCsv = get(p, "audit.csv", "results/fota_audit.csv");
		String firmwareJson = get(p, "firmware.json", "input/servers.json");

		String loginUrl = get(p, "login.url", "http://aepl-tcu4g-qa.accoladeelectronics.com:6102/login");
		String user = get(p, "login.user", "suraj.bhalerao@accoladeelectronics.com");
		String pass = get(p, "login.pass", "AD_QA_4G");
		String deviceId = get(p, "device.id", "ATCU1234");
		String state = get(p, "state", "Default");

		try {
			Path csvPath = Paths.get(firmwareCsv);
			if (Files.notExists(csvPath)) {
				Path fallback = Paths.get("input").resolve(firmwareCsv);
				if (Files.exists(fallback)) {
					logger.info("[LNC] Firmware CSV not found at {}, using fallback: {}", firmwareCsv, fallback);
					firmwareCsv = fallback.toString();
				}
			}

			Orchestrator orch = new Orchestrator(serialPort, baud, chromeDriver, firmwareCsv, auditCsv, firmwareJson,
					state);
			orch.start(loginUrl, user, pass, deviceId);
		} catch (Exception e) {
			logger.fatal("Fatal error starting orchestrator: {}", e.getMessage(), e);
			System.err.println("FATAL: " + e.getMessage());
			e.printStackTrace();
			System.exit(2);
		}
	}

	/**
	 * Initializes the required project directories and moves configuration files if
	 * necessary.
	 * Ensures that 'input', 'output', 'logs', 'screenshots', and 'results' folders
	 * exist.
	 * 
	 * NOTE: If 'fota_list.csv' is found in the root directory but not in the
	 * 'input' folder,
	 * it will be automatically moved to 'input/'.
	 */
	private static void setupDirectories() {
		String[] dirs = { "input", "output", "logs", "screenshots", "results" };
		for (String d : dirs) {
			try {
				Files.createDirectories(Paths.get(d));
			} catch (Exception e) {
				logger.error("Failed to create directory {}: {}", d, e.getMessage());
			}
		}

		try {
			Path rootCsv = Paths.get("fota_list.csv");
			Path inputCsv = Paths.get("input/fota_list.csv");
			if (Files.exists(rootCsv) && Files.notExists(inputCsv)) {
				Files.move(rootCsv, inputCsv);
				logger.info("Moved matching fota_list.csv to input/ folder.");
			}
		} catch (Exception e) {
			logger.warn("Warning: could not move fota_list.csv: {}", e.getMessage());
		}
	}

	/**
	 * Retrieves a configuration value with fallback support for environment
	 * variables and defaults.
	 * 
	 * @param p   The Properties object containing file-based config
	 * @param key The configuration key to look up
	 * @param def The default value if neither config nor env var is found
	 * @return The resolved configuration string
	 */
	private static String get(Properties p, String key, String def) {
		String v = p.getProperty(key);
		if (v != null && !v.trim().isEmpty())
			return v.trim();
		String envKey = key.toUpperCase().replace('.', '_');
		String env = System.getenv(envKey);
		if (env != null && !env.trim().isEmpty())
			return env.trim();
		return def;
	}
}
