package com.aepl.atcu.web;

import java.io.File;
import java.time.Duration;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

/**
 * Selenium-based web client for automating FOTA batch creation and monitoring.
 * It handles portal authentication, file uploads, and real-time status tracking
 * via the browser.
 * 
 * NOTE: The client uses explicit waits to handle asynchronous UI updates and
 * takes automatic screenshots during critical steps or failures.
 */
public class FotaWebClient implements AutoCloseable {
	private final WebDriver driver;
	private final WebDriverWait wait;
	private static final Logger logger = LogManager.getLogger(FotaWebClient.class);

	/**
	 * Initializes the Selenium WebDriver with custom options.
	 * 
	 * @param chromeDriverPath Path to the chromedriver executable
	 */
	public FotaWebClient(String chromeDriverPath) {
		if (chromeDriverPath != null && !chromeDriverPath.trim().isEmpty()) {
			System.setProperty("webdriver.chrome.driver", chromeDriverPath);
			logger.info("Using explicit webdriver.chrome.driver path: {}", chromeDriverPath);
		} else {
			logger.info("No webdriver.chrome.driver path configured. Using Selenium Manager auto driver resolution.");
		}

		ChromeOptions options = new ChromeOptions();
		options.addArguments("--start-maximized");
		options.addArguments("--remote-allow-origins=*");
		options.addArguments("--disable-notifications");

		logger.info("Starting ChromeDriver...");
		this.driver = new ChromeDriver(options);
		logger.info("ChromeDriver started successfully.");
		this.wait = new WebDriverWait(driver, Duration.ofSeconds(30));
	}

	/**
	 * Navigates to the portal and performs user login.
	 * 
	 * NOTE: It sets the page zoom to 67% after navigation to ensure all UI elements
	 * are visible and clickable on smaller screens or different resolutions.
	 * 
	 * @param url  The portal login URL
	 * @param user Username
	 * @param pass Password
	 */
	public void login(String url, String user, String pass) {
		logger.info("Navigating to login page: {}", url);
		driver.get(url);

		try {
			((JavascriptExecutor) driver).executeScript("document.body.style.zoom='50%'");
		} catch (Exception e) {
			logger.warn("Failed to set zoom level: {}", e.getMessage());
		}

		logger.info("Entering email and password...");
		wait.until(ExpectedConditions.visibilityOfElementLocated(By.id("email"))).sendKeys(user);
		driver.findElement(By.id("password")).sendKeys(pass);

		takeScreenshot("login_page_filled");

		logger.info("Clicking login button...");
		wait.until(ExpectedConditions.elementToBeClickable(By.className("submit-button"))).click();

		logger.info("Waiting for dashboard redirect...");
		try {
			wait.until(ExpectedConditions.urlContains("device-dashboard"));
			logger.info("Login successful. URL: {}", driver.getCurrentUrl());
		} catch (Exception e) {
			logger.error("Login verification failed. Current URL: {}", driver.getCurrentUrl());
			takeScreenshot("login_failed");
			throw e;
		}
		takeScreenshot("login_success");
	}

	/**
	 * Automates the creation of a new FOTA batch by filling the form and uploading
	 * a CSV.
	 * 
	 * @param batchName   Unique name for the batch
	 * @param description Detailed description of the batch
	 * @param filePath    Path to the CSV file containing device UINs
	 * @return True if the batch was created and successfully started
	 */
	public boolean createBatch(String batchName, String description, String filePath) {
		logger.info("Creating batch: {}", batchName);

		WebElement deviceUtilityMenu = wait
				.until(ExpectedConditions.elementToBeClickable(By.xpath("//*[contains(text(), 'Device Utility')]")));
		deviceUtilityMenu.click();

		WebElement fota_link = wait.until(ExpectedConditions.elementToBeClickable(By.linkText("FOTA")));
		fota_link.click();

		WebElement createBatchLink = wait.until(ExpectedConditions.elementToBeClickable(By.xpath(
				"//*[contains(text(), 'Create New Batch')]")));
		createBatchLink.click();

		wait.until(ExpectedConditions.visibilityOfElementLocated(By.xpath("//input[@placeholder='Batch Name']")))
				.sendKeys(batchName);

		wait.until(ExpectedConditions.visibilityOfElementLocated(By.xpath("//input[@placeholder='Batch Description']")))
				.sendKeys(description);

		WebElement select = wait
				.until(ExpectedConditions.elementToBeClickable(By.xpath("//mat-select[@formcontrolname='AIS140']")));
		select.click();
		wait.until(ExpectedConditions.elementToBeClickable(By.xpath("//span[contains(text(), 'AIS140 FOTA')]")))
				.click();

		WebElement fileInput = wait
				.until(ExpectedConditions.presenceOfElementLocated(By.xpath("//input[@type='file']")));
		fileInput.sendKeys(filePath);

		WebElement createBtn = wait
				.until(ExpectedConditions.elementToBeClickable(By.xpath("//button[contains(text(), 'Create Batch')]")));
		createBtn.click();

		logger.info("Batch creation form submitted.");
		takeScreenshot("batch_submitted");

		((JavascriptExecutor) driver).executeScript("window.scrollTo(0, document.body.scrollHeight);");
		wait.until(ExpectedConditions.elementToBeClickable(By.xpath("//button[contains(text(), 'Start') or contains(text(), 'Run') or .//mat-icon[contains(text(), 'play')]]"))).click();

		// wait.until(ExpectedConditions.visibilityOfElementLocated(By.xpath("//*[contains(text(), 'FOTA Batch List')]")));

		return startFotaBatch(batchName);
	}

	/**
	 * Locates a specific batch by name in the list and initiates the FOTA process.
	 * 
	 * @param targetBatchName The name of the batch to start
	 * @return True if the batch completes reaching 100% progress
	 */
	public boolean startFotaBatch(String targetBatchName) {
		driver.navigate().back();
		
		logger.info("Starting FOTA batch for: {}", targetBatchName);

		String rowXPath = String.format("//table/tbody/tr[td[contains(text(), '%s')]]", targetBatchName);
		WebElement batchRow = wait.until(ExpectedConditions.visibilityOfElementLocated(By.xpath(rowXPath)));

		String createdBy = "Unknown";
		try {
			WebElement createdByCell = batchRow.findElement(By.xpath("./td[4]"));
			createdBy = createdByCell.getText();
		} catch (Exception e) {
			logger.warn("Could not determine 'Created By' from column 4.");
		}

		if (createdBy == null || createdBy.isEmpty()) {
			createdBy = "Unknown";
		}

		try {
			WebElement visibilityBtn = batchRow
					.findElement(By.xpath(".//button[.//mat-icon[contains(text(),'visibility')]]"));
			if (visibilityBtn.isDisplayed()) {
				visibilityBtn.click();
				logger.info("Clicked visibility icon for batch row.");
			}
		} catch (Exception e) {
			logger.debug("No visibility icon found or already visible.");
		}

		logger.info("Batch verified. Created by: {}", createdBy);

		WebElement startBtn = wait.until(ExpectedConditions.elementToBeClickable(batchRow.findElement(By.xpath(
				".//button[contains(text(), 'Start') or contains(text(), 'Run') or .//mat-icon[contains(text(), 'play')]]"))));
		startBtn.click();

		try {
			return monitorBatch(targetBatchName);
		} catch (InterruptedException e) {
			logger.error("Monitoring batch interrupted: {}", e.getMessage());
			Thread.currentThread().interrupt();
			return false;
		}
	}

	/**
	 * Periodically refreshes the page and checks the status of a specific FOTA
	 * batch.
	 * 
	 * NOTE: This method will time out after approximately 30 minutes if completion
	 * is not reached.
	 * 
	 * @param batchName The batch to monitor
	 * @return True if status becomes 'Completed' and progress is 100%
	 * @throws InterruptedException If the sleep interval is interrupted
	 */
	public boolean monitorBatch(String batchName) throws InterruptedException {
		driver.navigate().refresh();
		logger.info("Monitoring batch: {}", batchName);

		for (int i = 0; i < 60; i++) {
			try {
				String rowXPath = String.format("//table/tbody/tr[td[contains(., '%s')]]", batchName);
				WebElement row = driver.findElement(By.xpath(rowXPath));
				String rowText = row.getText();
				logger.info("Batch Row Status: " + rowText);

				if (rowText.contains("Completed") && rowText.contains("100.00 %")) {
					logger.info("Batch {} is Completed.", batchName);
					takeScreenshot("batch_completed");
					return true;
				}
			} catch (Exception e) {
				logger.warn("Batch row not found yet or error reading: {}", e.getMessage());
			}

			Thread.sleep(30000);
			driver.navigate().refresh();
			wait.until(ExpectedConditions.visibilityOfElementLocated(By.xpath("//table")));
		}

		return false;
	}

	/**
	 * Captures a screenshot and saves it to the 'screenshots/' directory with a
	 * timestamp.
	 * 
	 * @param name Descriptive name for the screenshot file
	 */
	private void takeScreenshot(String name) {
		try {
			File src = ((org.openqa.selenium.TakesScreenshot) driver)
					.getScreenshotAs(org.openqa.selenium.OutputType.FILE);
			String timestamp = new java.text.SimpleDateFormat("yyyyMMdd_HHmmss").format(new java.util.Date());
			String destPath = "screenshots/" + name + "_" + timestamp + ".png";
			new File("screenshots").mkdirs();
			org.openqa.selenium.io.FileHandler.copy(src, new File(destPath));
			logger.info("Saved screenshot: {}", destPath);
		} catch (Exception e) {
			logger.warn("Failed to take screenshot: {}", e.getMessage());
		}
	}

	/**
	 * Closes the browser and terminates the WebDriver session.
	 */
	@Override
	public void close() {
		if (driver != null) {
			driver.quit();
		}
	}
}
