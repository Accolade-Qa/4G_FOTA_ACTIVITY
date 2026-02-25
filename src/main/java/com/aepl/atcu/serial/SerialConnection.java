package com.aepl.atcu.serial;

import com.fazecast.jSerialComm.SerialPort;
import com.fazecast.jSerialComm.SerialPortDataListener;
import com.fazecast.jSerialComm.SerialPortEvent;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.function.Consumer;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Low-level serial port wrapper using jSerialComm library.
 * Manages port configuration, connection lifecycle, and asynchronous data
 * reading/writing.
 */
public class SerialConnection implements AutoCloseable {

    private static final Logger logger = LogManager.getLogger(SerialConnection.class);
    private static final int OPEN_RETRY_COUNT = 5;
    private static final long OPEN_RETRY_DELAY_MS = 1000L;
    private static final long ACTIVITY_PROBE_MS = 3000L;
    private static final long ACTIVITY_POLL_MS = 100L;
    private final String requestedPortName;
    private final int baudRate;
    private SerialPort port;
    private String lastAttemptedPortName;
    private final List<String> attemptedPortNames = new ArrayList<>();
    private Consumer<String> dataCallback;

    /**
     * Initializes the serial port with standard 8N1 configuration and non-blocking
     * timeouts.
     * 
     * @param portName The system port name (e.g., "COM1" or "/dev/ttyUSB0")
     * @param baud     The communication baud rate
     */
    public SerialConnection(String portName, int baud) {
        this.requestedPortName = portName;
        this.baudRate = baud;
    }

    /**
     * Sets the callback function to be executed when new data is received from the
     * device.
     * 
     * @param callback A consumer function taking a String (data chunk)
     */
    public void setDataCallback(Consumer<String> callback) {
        this.dataCallback = callback;
    }

    /**
     * attempts to open the serial port and attaches the event listener.
     * 
     * NOTE: If opening fails, all available system ports are logged for
     * troubleshooting.
     * 
     * @return True if port was successfully opened, false otherwise
     */
    public boolean open() {
        attemptedPortNames.clear();
        lastAttemptedPortName = null;
        List<SerialPort> candidates = getCandidatePorts();
        if (isAutoRequested()) {
            SerialPort activePort = detectActivePort(candidates);
            if (activePort != null) {
                List<SerialPort> activeOnly = new ArrayList<>();
                activeOnly.add(activePort);
                candidates = activeOnly;
                logger.info("Selected active serial port based on incoming data: {} ({})",
                        activePort.getSystemPortName(), safeName(activePort.getDescriptivePortName()));
            } else {
                logger.warn("No active serial data detected during probe. Falling back to candidate order.");
            }
        }
        for (SerialPort candidate : candidates) {
            this.lastAttemptedPortName = candidate.getSystemPortName();
            attemptedPortNames.add(candidate.getSystemPortName());
            configurePort(candidate);
            for (int attempt = 1; attempt <= OPEN_RETRY_COUNT; attempt++) {
                if (candidate.openPort()) {
                    this.port = candidate;
                    logger.info("Successfully opened port {} ({})", port.getSystemPortName(),
                            safeName(port.getDescriptivePortName()));
                    setupListener();
                    return true;
                }
                if (attempt < OPEN_RETRY_COUNT) {
                    logger.warn("Open failed for {} (attempt {}/{}). Retrying in {} ms...", candidate.getSystemPortName(),
                            attempt, OPEN_RETRY_COUNT, OPEN_RETRY_DELAY_MS);
                    try {
                        Thread.sleep(OPEN_RETRY_DELAY_MS);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        return false;
                    }
                }
            }
            logger.warn("Could not open candidate port {} ({})", candidate.getSystemPortName(),
                    safeName(candidate.getDescriptivePortName()));
        }
        String requested = (requestedPortName == null || requestedPortName.trim().isEmpty()) ? "AUTO"
                : requestedPortName.trim();
        logger.error("Failed to open serial port. Requested='{}'. Tried='{}'. Available ports are:", requested,
                getAttemptedPortsSummary());
        for (SerialPort p : SerialPort.getCommPorts()) {
            logger.error(" - {} ({})", p.getSystemPortName(), p.getDescriptivePortName());
        }
        return false;
    }

    public boolean isOpen() {
        return port != null && port.isOpen();
    }

    public String getPortName() {
        if (port != null) {
            return port.getSystemPortName();
        }
        if (lastAttemptedPortName != null && !lastAttemptedPortName.trim().isEmpty()) {
            return lastAttemptedPortName;
        }
        if (requestedPortName != null && !requestedPortName.trim().isEmpty()) {
            return requestedPortName;
        }
        return "UNKNOWN";
    }

    public String getSystemPortName() {
        return getPortName();
    }

    public String getAttemptedPortsSummary() {
        if (attemptedPortNames.isEmpty()) {
            return "none";
        }
        return String.join(", ", attemptedPortNames);
    }

    private boolean isAutoRequested() {
        return requestedPortName == null || requestedPortName.trim().isEmpty();
    }

    /**
     * Writes a command string to the serial port followed by CRLF.
     * 
     * @param cmd The command string to send
     */
    public void writeEvent(String cmd) {
        if (isOpen()) {
            logger.debug("Writing to serial: {}", cmd);
            byte[] bytes = (cmd + "\r\n").getBytes(StandardCharsets.UTF_8);
            port.writeBytes(bytes, bytes.length);
        } else {
            logger.warn("Attempted to write to closed port {}", getPortName());
        }
    }

    /**
     * Configures a background listener for the DATA_AVAILABLE event.
     * Reads incoming bytes into a buffer and passes them to the data callback.
     */
    private void setupListener() {
        port.addDataListener(new SerialPortDataListener() {
            @Override
            public int getListeningEvents() {
                return SerialPort.LISTENING_EVENT_DATA_AVAILABLE;
            }

            @Override
            public void serialEvent(SerialPortEvent event) {
                if (event.getEventType() != SerialPort.LISTENING_EVENT_DATA_AVAILABLE)
                    return;
                int available = port.bytesAvailable();
                if (available <= 0)
                    return;
                byte[] buffer = new byte[available];
                int read = port.readBytes(buffer, buffer.length);
                if (read > 0 && dataCallback != null) {
                    String chunk = new String(buffer, 0, read, StandardCharsets.UTF_8);
                    dataCallback.accept(chunk);
                }
            }
        });
    }

    /**
     * Removes listeners and closes the port connection.
     */
    @Override
    public void close() {
        try {
            if (port != null) {
                port.removeDataListener();
            }
            if (port != null && port.isOpen()) {
                port.closePort();
                logger.info("Closed port {}", port.getSystemPortName());
            }
        } catch (Exception e) {
            logger.error("Error closing port {}: {}", getPortName(), e.getMessage());
        }
    }

    private void configurePort(SerialPort targetPort) {
        targetPort.setBaudRate(baudRate);
        targetPort.setNumDataBits(8);
        targetPort.setNumStopBits(SerialPort.ONE_STOP_BIT);
        targetPort.setParity(SerialPort.NO_PARITY);
        targetPort.setComPortTimeouts(SerialPort.TIMEOUT_NONBLOCKING, 0, 0);
    }

    private List<SerialPort> getCandidatePorts() {
        SerialPort[] allPorts = SerialPort.getCommPorts();
        List<SerialPort> candidates = new ArrayList<>();
        if (allPorts == null || allPorts.length == 0) {
            return candidates;
        }

        String preferred = (requestedPortName == null) ? "" : requestedPortName.trim();
        if (!preferred.isEmpty()) {
            for (SerialPort p : allPorts) {
                if (preferred.equalsIgnoreCase(p.getSystemPortName())) {
                    candidates.add(p);
                    break;
                }
            }
            logger.info("Explicit serial.port configured ({}). Restricting candidates to requested port only.",
                    preferred);
            if (candidates.isEmpty()) {
                logger.warn("Requested port {} not found in current system port list.", preferred);
            }
            return candidates;
        }

        List<SerialPort> ranked = new ArrayList<>();
        for (SerialPort p : allPorts) {
            if (candidates.contains(p)) {
                continue;
            }
            ranked.add(p);
        }
        ranked.sort(Comparator.comparingInt(this::portPriority).reversed());
        candidates.addAll(ranked);

        logger.info("Serial port candidates (in order):");
        for (SerialPort p : candidates) {
            logger.info(" - {} ({})", p.getSystemPortName(), safeName(p.getDescriptivePortName()));
        }
        return candidates;
    }

    private SerialPort detectActivePort(List<SerialPort> candidates) {
        for (SerialPort candidate : candidates) {
            configurePort(candidate);
            if (!candidate.openPort()) {
                continue;
            }
            try {
                long end = System.currentTimeMillis() + ACTIVITY_PROBE_MS;
                while (System.currentTimeMillis() < end) {
                    int available = candidate.bytesAvailable();
                    if (available > 0) {
                        int toRead = Math.min(available, 512);
                        byte[] buffer = new byte[toRead];
                        int read = candidate.readBytes(buffer, buffer.length);
                        if (read > 0) {
                            String chunk = new String(buffer, 0, read, StandardCharsets.UTF_8).trim();
                            if (!chunk.isEmpty()) {
                                return candidate;
                            }
                        }
                    }
                    Thread.sleep(ACTIVITY_POLL_MS);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return null;
            } finally {
                try {
                    if (candidate.isOpen()) {
                        candidate.closePort();
                    }
                } catch (Exception ignored) {
                }
            }
        }
        return null;
    }

    private int portPriority(SerialPort p) {
        String desc = safeName(p.getDescriptivePortName()).toLowerCase(Locale.ROOT);
        int score = 0;
        if (desc.contains("usb")) {
            score += 20;
        }
        if (desc.contains("serial")) {
            score += 8;
        }
        if (desc.contains("prolific") || desc.contains("ch340") || desc.contains("ftdi")
                || desc.contains("cp210") || desc.contains("silicon labs")) {
            score += 15;
        }
        if (desc.contains("bluetooth")) {
            score -= 30;
        }
        return score;
    }

    private String safeName(String value) {
        return (value == null || value.trim().isEmpty()) ? "Unknown" : value;
    }
}
