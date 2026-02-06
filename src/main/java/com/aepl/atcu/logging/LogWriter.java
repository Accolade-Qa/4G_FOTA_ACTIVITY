package com.aepl.atcu.logging;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Handles the background logging of serial data.
 * It uses a producer-consumer pattern via a BlockingQueue to ensure that the
 * serial data parsing
 * is not blocked by I/O or formatting operations.
 * 
 * NOTE: This class formats raw serial strings into structured log lines with
 * aligned columns
 * for improved readability in the terminal and log files.
 */
public class LogWriter implements AutoCloseable {

    private static final Logger logger = LogManager.getLogger(LogWriter.class);
    private static final Logger serialLogger = LogManager.getLogger("com.aepl.atcu.logging.SerialLogger");
    private final BlockingQueue<String> queue = new LinkedBlockingQueue<>(20000);
    private final ExecutorService executor;
    private String logFilename = null;

    /**
     * Regex pattern to parse structured device logs.
     * Captures timestamp, log level, tag/component, and the actual message.
     */
    private static final Pattern LOG_PARSE = Pattern
            .compile("^(\\S+)\\s*(?:([A-Z]+):\\s*)?(?:\\s*\\[([^\\]]+)\\]\\s*)?(.*)$");

    /**
     * Initializes the LogWriter with a single-threaded background executor.
     */
    public LogWriter() {
        this.executor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "log-writer");
            t.setDaemon(true);
            return t;
        });
    }

    /**
     * Sets the IMEI and initializes the serial log filename.
     * Format: AUTO_{IMEI}_{DATE}_{TIME}.log
     */
    public synchronized void setImei(String imei) {
        if (imei == null || imei.isEmpty())
            return;
        String timestamp = new java.text.SimpleDateFormat("yyyyMMdd_HHmmss").format(new java.util.Date());
        this.logFilename = String.format("AUTO_%s_%s.log", imei, timestamp);
        logger.info("Serial log initialized: {}", logFilename);
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

    /**
     * The continuous consumer loop that takes lines from the queue and logs them.
     */
    private void writeLoop() {
        try {
            while (!Thread.currentThread().isInterrupted()) {
                String raw = queue.take();
                String formatted = formatLogLine(raw);

                // Write to program log (console + program_progress.log)
                logger.info(formatted);

                // Write to separate serial log if filename is initialized
                if (logFilename != null) {
                    org.apache.logging.log4j.ThreadContext.put("serial_filename", logFilename);
                    serialLogger.info(formatted);
                    org.apache.logging.log4j.ThreadContext.remove("serial_filename");
                }
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    /**
     * Parses and aligns columns in a raw log line.
     * 
     * @param raw The raw timestamped line
     * @return A formatted string with consistent spacing for columns
     */
    private String formatLogLine(String raw) {
        if (raw == null)
            return "";
        Matcher m = LOG_PARSE.matcher(raw);
        if (!m.matches())
            return raw;

        String ts = safeOrEmpty(m.group(1));
        String level = safeOrEmpty(m.group(2));
        String tag = safeOrEmpty(m.group(3));
        String msg = safeOrEmpty(m.group(4));

        String tagOut = tag.isEmpty() ? "" : "[" + tag + "]";

        return String.format("%s %s %s %s",
                padRight(ts, 27),
                padRight(level, 6),
                padRight(tagOut, 12),
                msg);
    }

    private static String safeOrEmpty(String s) {
        return (s == null) ? "" : s;
    }

    /**
     * Utility to pad a string to a specific width for column alignment.
     * 
     * @param s     The input string
     * @param width The target width
     * @return Padded or truncated string
     */
    private static String padRight(String s, int width) {
        if (s == null)
            s = "";
        if (s.length() >= width)
            return s.substring(0, width);
        StringBuilder sb = new StringBuilder(s);
        while (sb.length() < width)
            sb.append(' ');
        return sb.toString();
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
