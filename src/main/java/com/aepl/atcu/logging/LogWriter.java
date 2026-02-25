package com.aepl.atcu.logging;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Handles the background logging of serial data.
 * It uses a producer-consumer pattern via a BlockingQueue to ensure that the
 * serial data parsing
 * is not blocked by I/O or formatting operations.
 * 
 * NOTE: Device lines are persisted in raw form; timestamp formatting is handled
 * by the logging configuration.
 */
public class LogWriter implements AutoCloseable {

    private static final Logger logger = LogManager.getLogger(LogWriter.class);
    private static final String DEFAULT_PREFIX = "AUTO_SESSION_";
    private static final DateTimeFormatter SERIAL_TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS");
    private final BlockingQueue<String> queue = new LinkedBlockingQueue<>(20000);
    private final ExecutorService executor;
    private String logFilename = null;

    /**
     * Initializes the LogWriter with a single-threaded background executor.
     */
    public LogWriter() {
        this.executor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "log-writer");
            t.setDaemon(true);
            return t;
        });
        initializeDefaultSerialLog();
    }

    /**
     * Sets the IMEI and initializes the serial log filename.
     * Format: AUTO_{IMEI}_{DATE}_{TIME}.log
     */
    public synchronized void setImei(String imei) {
        if (imei == null || imei.isEmpty())
            return;
        String timestamp = buildTimestamp();
        String imeiFile = String.format("AUTO_%s_%s.log", imei, timestamp);
        if (!imeiFile.equals(this.logFilename)) {
            this.logFilename = imeiFile;
            ensureSerialFileExists();
            logger.info("Serial log switched to IMEI file: {}", logFilename);
        }
    }

    /**
     * Starts the background log-writing loop.
     */
    public void start() {
        executor.submit(this::writeLoop);
    }

    /**
     * Enqueues a raw log line for processing.
     * 
     * @param line The raw string received from the device
     */
    public void log(String line) {
        if (line != null && !line.isEmpty()) {
            boolean ok = queue.offer(line);
            if (!ok) {
                logger.warn("Log queue full, dropping: {}", line);
            }
        }
    }

    private synchronized void initializeDefaultSerialLog() {
        if (this.logFilename == null || this.logFilename.trim().isEmpty()) {
            this.logFilename = DEFAULT_PREFIX + buildTimestamp() + ".log";
            ensureSerialFileExists();
            logger.info("Serial log initialized: {}", logFilename);
        }
    }

    private static String buildTimestamp() {
        return new java.text.SimpleDateFormat("yyyyMMdd_HHmmss").format(new java.util.Date());
    }

    private synchronized void ensureSerialFileExists() {
        if (this.logFilename == null || this.logFilename.trim().isEmpty()) {
            return;
        }
        try {
            Path logDir = Paths.get("logs");
            Files.createDirectories(logDir);
            Path serialPath = logDir.resolve(this.logFilename);
            if (Files.notExists(serialPath)) {
                Files.createFile(serialPath);
            }
        } catch (IOException e) {
            logger.warn("Failed to create serial log file '{}': {}", this.logFilename, e.getMessage());
        }
    }

    private void writeToSerialFile(String message) {
        String fileNameSnapshot;
        synchronized (this) {
            fileNameSnapshot = this.logFilename;
        }
        if (fileNameSnapshot == null || fileNameSnapshot.trim().isEmpty()) {
            return;
        }
        try {
            Path logDir = Paths.get("logs");
            Files.createDirectories(logDir);
            Path serialPath = logDir.resolve(fileNameSnapshot);
            String line = LocalDateTime.now().format(SERIAL_TS) + " " + message + System.lineSeparator();
            Files.writeString(serialPath, line, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException e) {
            logger.warn("Failed writing serial log file: {}", e.getMessage());
        }
    }

    /**
     * The continuous consumer loop that takes lines from the queue and logs them.
     */
    private void writeLoop() {
        try {
            while (!Thread.currentThread().isInterrupted()) {
                String raw = queue.take();
                String formatted = raw.trim();
                if (formatted.isEmpty()) {
                    continue;
                }

                // Write to program log (console + program_progress.log)
                logger.info(formatted);

                writeToSerialFile(formatted);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    /**
     * Shuts down the background executor gracefully.
     */
    @Override
    public void close() {
        executor.shutdown();
        try {
            executor.awaitTermination(3, TimeUnit.SECONDS);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
    }
}
