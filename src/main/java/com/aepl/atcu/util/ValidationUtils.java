package com.aepl.atcu.util;

import java.util.regex.Pattern;

public class ValidationUtils {

    private static final String UIN_PREFIX = "ACON";
    private static final Pattern IMEI_PATTERN = Pattern.compile("^\\d{13,15}$");

    public static boolean isValidUin(String uin) {
        return uin != null && !uin.isEmpty() && uin.startsWith(UIN_PREFIX);
    }

    public static boolean isValidImei(String imei) {
        return imei != null && !imei.isEmpty() && IMEI_PATTERN.matcher(imei).matches();
    }

    private ValidationUtils() {
        // Utility class
    }
}