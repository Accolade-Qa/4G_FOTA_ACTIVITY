package com.aepl.atcu.util;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;

public class LoginPacketInfo {
    public final String imei;
    public final String iccid;
    public final String uin;
    public final String version;
    public final String vin;
    public final String model;
    @JsonIgnore
    public final String state;

    @JsonCreator
    public LoginPacketInfo(
            @JsonProperty("imei") String imei,
            @JsonProperty("iccid") String iccid,
            @JsonProperty("uin") String uin,
            @JsonProperty("version") String version,
            @JsonProperty("vin") String vin,
            @JsonProperty("model") String model,
            String state) {
		this.imei = imei;
		this.iccid = iccid;
		this.uin = uin;
		this.version = version;
		this.vin = vin;
		this.model = (model == null || model.isEmpty()) ? "4G" : model;
		this.state = state;
	}

	public String[] toCsvRow() {
		return new String[] { uin, version, model, imei, state };
	}
}
