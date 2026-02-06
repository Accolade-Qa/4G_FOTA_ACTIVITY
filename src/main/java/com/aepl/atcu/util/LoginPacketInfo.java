package com.aepl.atcu.util;

/**
 * Data model for device login packet information extracted from serial output.
 * It encapsulates device identity (IMEI, ICCID, UIN), firmware versions, and
 * state metadata.
 */
public class LoginPacketInfo {
	public final String imei;
	public final String iccid;
	public final String uin;
	public final String version;
	public final String vin;
	public final String model;
	public final String state;

	/**
	 * Constructs a new LoginPacketInfo with provided device details.
	 * 
	 * @param imei    International Mobile Equipment Identity
	 * @param iccid   Integrated Circuit Card Identifier
	 * @param uin     Unique Identification Number
	 * @param version Current software version reported by the device
	 * @param vin     Vehicle Identification Number
	 * @param model   Device model (defaults to "4G" if empty)
	 * @param state   Device state (defaults to "Default" if empty)
	 */
	public LoginPacketInfo(String imei, String iccid, String uin, String version, String vin, String model,
			String state) {
		this.imei = imei;
		this.iccid = iccid;
		this.uin = uin;
		this.version = version;
		this.vin = vin;
		this.model = (model == null || model.isEmpty()) ? "4G" : model;
		this.state = (state == null || state.isEmpty()) ? "Default" : state;
	}

	/**
	 * Maps the object fields to a generic CSV row format compatible with batch
	 * upload.
	 * 
	 * @return Array of strings representing a CSV row.
	 */
	public String[] toCsvRow() {
		return new String[] { uin, version, model, state, imei };
	}
}
