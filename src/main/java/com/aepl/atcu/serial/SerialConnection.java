package com.aepl.atcu.serial;

import com.fazecast.jSerialComm.SerialPort;
import com.fazecast.jSerialComm.SerialPortDataListener;
import com.fazecast.jSerialComm.SerialPortEvent;
import java.nio.charset.StandardCharsets;
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
    private final SerialPort port;
    private final String portName;
    private Consumer<String> dataCallback;

    /**
     * Initializes the serial port with standard 8N1 configuration and non-blocking
     * timeouts.
     * 
     * @param portName The system port name (e.g., "COM1" or "/dev/ttyUSB0")
     * @param baud     The communication baud rate
     */
    public SerialConnection(String portName, int baud) {
        this.portName = portName;
        this.port = SerialPort.getCommPort(portName);
        this.port.setBaudRate(baud);
        this.port.setNumDataBits(8);
        this.port.setNumStopBits(SerialPort.ONE_STOP_BIT);
        this.port.setParity(SerialPort.NO_PARITY);
        this.port.setComPortTimeouts(SerialPort.TIMEOUT_NONBLOCKING, 0, 0);
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
        if (port.openPort()) {
            logger.info("Successfully opened port {} (system name: {})", portName, port.getSystemPortName());
            setupListener();
            return true;
        }
        logger.error("Failed to open port {}. Available ports are:", portName);
        for (SerialPort p : SerialPort.getCommPorts()) {
            logger.error(" - {} ({})", p.getSystemPortName(), p.getDescriptivePortName());
        }
        return false;
    }

    public boolean isOpen() {
        return port.isOpen();
    }

    public String getPortName() {
        return portName;
    }

    public String getSystemPortName() {
        return port.getSystemPortName();
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
            logger.warn("Attempted to write to closed port {}", portName);
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
            port.removeDataListener();
            if (port.isOpen()) {
                port.closePort();
                logger.info("Closed port {}", portName);
            }
        } catch (Exception e) {
            logger.error("Error closing port {}: {}", portName, e.getMessage());
        }
    }
}
