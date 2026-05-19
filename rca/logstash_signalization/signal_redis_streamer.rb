require "json"
require "redis"

def register(params)
    @enabled = to_bool(params["enabled"], true)

    address = params["address"] || "127.0.0.1:6379"
    address_parts = address.split(":")

    @host = address_parts[0]
    @port = (address_parts[1] || 6379).to_i

    @username = blank_to_nil(params["username"])
    @password = blank_to_nil(params["password"])
    @db = (params["db"] || 0).to_i

    @dial_timeout = parse_seconds(params["dial_timeout_seconds"], 5)
    @read_timeout = parse_seconds(params["read_timeout_seconds"], 3)
    @write_timeout = parse_seconds(params["write_timeout_seconds"], 3)

    @stream_key_prefix = params["stream_key"] || "Rca:signalized_log_events"
    @max_len = (params["max_len"] || 100000).to_i

    # 30 minutes = 1800 seconds
    @window_seconds = (params["window_seconds"] || 1800).to_i

    @trim_every_seconds = (params["trim_every_seconds"] || 10).to_i

    @redis = nil
end

def filter(event)
    return [event] unless @enabled
    return [event] if event.get("signal").nil?

    begin
        connect_redis if @redis.nil?

        payload = build_payload(event)
        stream_key = stream_key_for(payload["signal"])

        @redis.xadd(
            stream_key,
            { "event" => payload.to_json },
            id: "*",
            maxlen: @max_len
        )

        trim_old_entries(stream_key)
        expire_quiet_stream(stream_key)

    rescue => e
        @redis = nil

        event.tag("_signal_redis_stream_error")
        event.set("[signal_stream_error][message]", e.message)
        event.set("[signal_stream_error][class]", e.class.to_s)
    end

    [event]
end

def connect_redis
    options = redis_options(@username, @password)

    begin
        @redis = Redis.new(options)
        @redis.ping
    rescue => e
        # Some Redis servers run without AUTH enabled. If the pipeline passes a
        # password anyway, retry once without credentials instead of failing the
        # whole Logstash pipeline during startup.
        if should_retry_without_auth?(e)
            @username = nil
            @password = nil

            @redis = Redis.new(redis_options(nil, nil))
            @redis.ping
        else
            raise
        end
    end
end

def redis_options(username, password)
    options = {
        host: @host,
        port: @port,
        db: @db,
        timeout: @dial_timeout,
        connect_timeout: @dial_timeout,
        read_timeout: @read_timeout,
        write_timeout: @write_timeout
    }

    options[:username] = username if username
    options[:password] = password if password

    options
end

def should_retry_without_auth?(error)
    message = error.message.to_s.downcase

    return false if @password.nil?

    message.include?("called without any password configured") ||
        message.include?("auth <password> called without any password configured") ||
        message.include?("client sent auth, but no password is set")
end

def trim_old_entries(stream_key)
    min_ms = ((Time.now.to_f - @window_seconds) * 1000).to_i
    min_stream_id = "#{min_ms}-0"

    @redis.xtrim(
        stream_key,
        min_stream_id,
        strategy: "MINID"
    )
end

def build_payload(event)
    payload = {
        "@timestamp" => event.get("@timestamp").to_s,
        "signal" => event.get("signal"),
        "source_rca_id" => event.get("source_rca_id"),
        "event" => compact_hash(
            "organization" => event.get("[event][organization]"),
            "module" => event.get("[event][module]")
        ),
        "log" => compact_hash(
            "level" => event.get("[log][level]")
        ),
        "host" => compact_hash(
            "ip" => event.get("[host][ip]"),
            "name" => event.get("[host][name]")
        )
    }

    payload.delete_if { |k, v| v.nil? }
    payload
end

def compact_hash(hash)
    hash.delete_if { |_, value| value.nil? || (value.respond_to?(:empty?) && value.empty?) }
    return nil if hash.empty?

    hash
end

def stream_key_for(signal)
    signal_value = blank_to_nil(signal)
    signal_value = "unknown" if signal_value.nil?

    "#{@stream_key_prefix}:signal:#{signal_value}"
end

def expire_quiet_stream(stream_key)
    @redis.expire(stream_key, @window_seconds)
end

def parse_seconds(value, default_value)
    return default_value.to_f if value.nil?

    text = value.to_s.strip

    return default_value.to_f if text.empty?

    if text.end_with?("ms")
        text.sub("ms", "").to_f / 1000.0
    elsif text.end_with?("s")
        text.sub("s", "").to_f
    else
        text.to_f
    end
end

def blank_to_nil(value)
    return nil if value.nil?

    value = value.to_s.strip

    return nil if value.empty?

    value
end

def to_bool(value, default_value)
    return default_value if value.nil?

    ["true", "1", "yes", "y"].include?(value.to_s.downcase)
end
