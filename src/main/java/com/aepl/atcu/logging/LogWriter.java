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

public class LogWriter implements AutoCloseable {

    private static final Logger logger = LogManager.getLogger(LogWriter.class);
    private static final String DEFAULT_PREFIX = "AUTO_FOTA_";
    private static final DateTimeFormatter SERIAL_TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS");
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyyMMdd");
    private final BlockingQueue<String> queue = new LinkedBlockingQueue<>(20000);
    private final ExecutorService executor;
    private String logFilename = null;

    public LogWriter() {
        this.executor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "log-writer");
            t.setDaemon(true);
            return t;
        });
        initializeDefaultSerialLog();
    }

    public synchronized void setImei(String imei) {
        if (imei == null || imei.isEmpty())
            return;
        String dateStamp = java.time.LocalDateTime.now().format(DATE_FORMAT);
        String imeiFile = String.format("AUTO_FOTA_%s_%s.log", imei, dateStamp);
        if (!imeiFile.equals(this.logFilename)) {
            this.logFilename = imeiFile;
            ensureSerialFileExists();
            logger.info("FOTA log switched to IMEI file: {}", logFilename);
        }
    }

    public void start() {
        executor.submit(this::writeLoop);
    }

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
            String dateStamp = java.time.LocalDateTime.now().format(DATE_FORMAT);
            this.logFilename = DEFAULT_PREFIX + "DEFAULT_" + dateStamp + ".log";
            ensureSerialFileExists();
            logger.info("FOTA log initialized: {}", logFilename);
        }
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

    private void writeLoop() {
        try {
            while (!Thread.currentThread().isInterrupted()) {
                String raw = queue.take();
                String formatted = raw.trim();
                if (formatted.isEmpty()) {
                    continue;
                }
                logger.info(formatted);

                writeToSerialFile(formatted);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

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
