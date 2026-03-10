package com.aepl.atcu.util;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public class LoginPacketStore {
    private static final Logger logger = LogManager.getLogger(LoginPacketStore.class);
    private static final ObjectMapper mapper = new ObjectMapper();

    public static void persist(String path, LoginPacketInfo info) {
        if (path == null || info == null) {
            return;
        }

        try {
            File file = new File(path);
            List<LoginPacketInfo> list;
            if (file.exists()) {
                try {
                    list = mapper.readValue(file, new TypeReference<List<LoginPacketInfo>>() {});
                } catch (IOException e) {
                    logger.warn("Failed to read existing login JSON, starting fresh: {}", e.getMessage());
                    list = new ArrayList<>();
                }
            } else {
                list = new ArrayList<>();
            }

            boolean exists = list.stream().anyMatch(e ->
                    Objects.equals(e.uin, info.uin) &&
                    Objects.equals(e.version, info.version) &&
                    Objects.equals(e.imei, info.imei));

            if (!exists) {
                list.add(info);
                mapper.writerWithDefaultPrettyPrinter().writeValue(file, list);
                logger.info("Appended login packet for UIN={} version={} to {}", info.uin, info.version, path);
            } else {
                logger.debug("Login packet already recorded: {}", info.uin);
            }
        } catch (Exception e) {
            logger.error("Unable to persist login packet to {}: {}", path, e.getMessage(), e);
        }
    }
    public static List<LoginPacketInfo> loadAll(String path) {
        if (path == null) {
            return new ArrayList<>();
        }
        try {
            File file = new File(path);
            if (!file.exists()) {
                return new ArrayList<>();
            }
            return mapper.readValue(file, new TypeReference<List<LoginPacketInfo>>() {});
        } catch (IOException e) {
            logger.warn("Could not load login packets from {}: {}", path, e.getMessage());
            return new ArrayList<>();
        }
    }
}