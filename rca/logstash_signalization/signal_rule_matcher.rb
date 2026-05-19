require "yaml"
require "securerandom"

def register(params)
    @rules_root = params["rules_root"] || "/etc/logstash/rules"
    @rules_by_module = {}

    @op_score = {
        "equals" => 50,
        "in" => 45,
        "regex" => 35,
        "contains" => 25,
        "gte" => 30,
        "lte" => 30,
        "gt" => 30,
        "lt" => 30,
        "exists" => 10,
        "not_equals" => 20,
        "not_regex" => 20
    }

    @level_score = {
        "critical" => 5,
        "error" => 4,
        "warning" => 3,
        "info" => 2,
        "debug" => 1
    }

    load_all_rules
end

def filter(event)
    module_name = event.get("[event][module]") || event.get("event.module")

    return [event] if module_name.nil?

    rules = @rules_by_module[module_name.to_s]

    return [event] if rules.nil? || rules.empty?

    best_rule = nil
    best_score = nil

    rules.each do |rule|
        next if rule.nil?
        next if rule["signal_key"].nil?

        matched, condition_score = condition_match(event, rule["condition"])

        next unless matched

        if rule["score"]
            final_score = rule["score"].to_i
        else
            final_score = condition_score
            final_score += @level_score[rule["level"].to_s] || 0
            final_score -= 10000 if fallback_rule?(rule)
        end

        if best_score.nil? || final_score > best_score
            best_score = final_score
            best_rule = rule
        end
    end

    if best_rule
        signal_key = best_rule["signal_key"].to_s
        rule_level = best_rule["level"]
        source_rca_id = ensure_source_rca_id(event)

        event.set("signal", signal_key)
        event.set("source_rca_id", source_rca_id)
        add_tag(event, signal_key)

        event.set("[signal_data][id]", best_rule["id"])
        event.set("[signal_data][score]", best_score)
        event.set("[signal_data][level]", rule_level)
        event.set("[signal_data][description]", best_rule["description"])
        event.set("[signal_data][tags]", best_rule["tags"])

        overwrite_log_level(event, rule_level)
    end

    [event]
end

def load_all_rules
    Dir.glob(File.join(@rules_root, "services", "*.yml")).each do |file_path|
        begin
            data = YAML.load_file(file_path) || {}
            module_name = data["service"] || File.basename(file_path, ".yml")

            rules = load_yaml_file(file_path)

            suggestion_file = File.join(@rules_root, "suggestions", "#{module_name}.yml")
            rules.concat(load_yaml_file(suggestion_file)) if File.exist?(suggestion_file)

            @rules_by_module[module_name.to_s] = rules
        rescue => e
            next
        end
    end
end

def load_yaml_file(file_path, loaded_files = {})
    return [] if loaded_files[file_path]

    loaded_files[file_path] = true

    data = YAML.load_file(file_path) || {}
    rules = []

    Array(data["imports"]).each do |import_path|
        full_import_path = File.expand_path(import_path, File.dirname(file_path))
        rules.concat(load_yaml_file(full_import_path, loaded_files)) if File.exist?(full_import_path)
    end

    rules.concat(Array(data["rules"]))

    rules
rescue => e
    []
end

def get_event_value(event, field)
    return nil if field.nil?

    path = "[" + field.to_s.split(".").join("][") + "]"
    value = event.get(path)

    value = event.get(field.to_s) if value.nil?

    value
end

def regex_match?(actual, pattern)
    return false if actual.nil? || pattern.nil?

    begin
        !!(actual.to_s =~ Regexp.new(pattern.to_s))
    rescue
        false
    end
end

def single_condition_match(event, condition)
    field = condition["field"]
    op = condition["op"]
    expected = condition["value"]
    actual = get_event_value(event, field)

    matched = false

    case op
    when "exists"
        matched = !actual.nil?

    when "equals"
        matched = !actual.nil? && actual.to_s == expected.to_s

    when "not_equals"
        matched = actual.nil? || actual.to_s != expected.to_s

    when "contains"
        matched = !actual.nil? && actual.to_s.include?(expected.to_s)

    when "regex"
        matched = regex_match?(actual, expected)

    when "not_regex"
        matched = !regex_match?(actual, expected)

    when "in"
        matched = !actual.nil? && Array(expected).map(&:to_s).include?(actual.to_s)

    when "gte"
        matched = !actual.nil? && actual.to_f >= expected.to_f

    when "lte"
        matched = !actual.nil? && actual.to_f <= expected.to_f

    when "gt"
        matched = !actual.nil? && actual.to_f > expected.to_f

    when "lt"
        matched = !actual.nil? && actual.to_f < expected.to_f
    end

    score = @op_score[op.to_s] || 1

    [matched, matched ? score : 0]
end

def condition_match(event, condition)
    return [false, 0] if condition.nil?

    if condition["and"]
        total_score = 0

        Array(condition["and"]).each do |child|
            matched, score = condition_match(event, child)
            return [false, 0] unless matched

            total_score += score
        end

        return [true, total_score]
    end

    if condition["or"]
        best_score = 0
        matched_any = false

        Array(condition["or"]).each do |child|
            matched, score = condition_match(event, child)

            if matched
                matched_any = true
                best_score = score if score > best_score
            end
        end

        return [matched_any, best_score]
    end

    single_condition_match(event, condition)
end

def fallback_rule?(rule)
    id = rule["id"].to_s
    tags = Array(rule["tags"]).map(&:to_s)

    id.start_with?("A_") || tags.include?("fallback") || tags.include?("unclassified")
end

def add_tag(event, tag)
    tags = event.get("tags")

    if tags.nil?
        tags = []
    elsif !tags.is_a?(Array)
        tags = [tags]
    end

    tags << tag
    event.set("tags", tags.uniq)
end

def overwrite_log_level(event, level)
    return if level.nil?

    event.set("[log][level]", level)
end

def ensure_source_rca_id(event)
    existing = event.get("source_rca_id")
    return existing unless existing.nil? || existing.to_s.strip.empty?

    generate_source_rca_id
end

def generate_source_rca_id
    SecureRandom.uuid
end
