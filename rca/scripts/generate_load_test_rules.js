const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..");
const SOURCE_RULES_FILE = path.join(REPO_ROOT, "log_correlation_engine", "rules", "rules.json");
const OUTPUT_DIR = path.join(REPO_ROOT, "dist", "load_test_rules");
const DEFAULT_OUTPUT_FILE = path.join(OUTPUT_DIR, "correlation_rules.load-test.json");

const DEFAULT_TOTAL_RULES = 1000;
const DEFAULT_HOT_RULE_ID = "CORR_PROD_RABBITMQ_CONNECTION_TO_EDGE_503";
const DEFAULT_HOT_RULE_COUNT = 250;

function readRules(filePath) {
  const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
  if (!Array.isArray(payload)) {
    throw new Error(`rules file must contain a JSON array: ${filePath}`);
  }
  return payload;
}

function ensureDirectory(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function makeBatchLabel() {
  return new Date().toISOString()
    .replace(/\.\d{3}Z$/, "Z")
    .replace(/[:\-]/g, "")
    .replace("T", "T");
}

function parseIntArg(value, fallback, label) {
  if (value === undefined) {
    return fallback;
  }
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${label} must be a positive integer`);
  }
  return parsed;
}

function parseArgs(argv) {
  const args = {
    output: DEFAULT_OUTPUT_FILE,
    total: DEFAULT_TOTAL_RULES,
    hotRuleId: DEFAULT_HOT_RULE_ID,
    hotCount: DEFAULT_HOT_RULE_COUNT,
  };

  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--output") {
      args.output = path.resolve(argv[++index]);
      continue;
    }
    if (token === "--total") {
      args.total = parseIntArg(argv[++index], DEFAULT_TOTAL_RULES, "--total");
      continue;
    }
    if (token === "--hot-rule-id") {
      args.hotRuleId = String(argv[++index] || "").trim();
      continue;
    }
    if (token === "--hot-count") {
      args.hotCount = parseIntArg(argv[++index], DEFAULT_HOT_RULE_COUNT, "--hot-count");
      continue;
    }
    throw new Error(`unknown argument: ${token}`);
  }

  if (!args.hotRuleId) {
    throw new Error("--hot-rule-id must not be empty");
  }
  if (args.hotCount > args.total) {
    throw new Error("--hot-count must be less than or equal to --total");
  }

  return args;
}

function buildDistribution(rules, total, hotRuleId, hotCount) {
  const hotRule = rules.find((rule) => String(rule.id || "").trim() === hotRuleId);
  if (!hotRule) {
    throw new Error(`hot rule not found in source rules: ${hotRuleId}`);
  }

  const distribution = [];
  for (let index = 0; index < hotCount; index += 1) {
    distribution.push(hotRule);
  }

  let cursor = 0;
  while (distribution.length < total) {
    distribution.push(rules[cursor % rules.length]);
    cursor += 1;
  }

  return distribution;
}

function createLoadTestRule(baseRule, ordinal, batchLabel) {
  const cloned = deepClone(baseRule);
  const suffix = String(ordinal).padStart(4, "0");
  cloned.id = `${baseRule.id}__LOAD_TEST_${batchLabel}_${suffix}`;
  cloned.is_enabled = true;
  cloned.load_test = true;
  cloned.load_test_batch = batchLabel;
  cloned.load_test_base_rule_id = baseRule.id;
  cloned.description = `[load_test ${batchLabel}] ${baseRule.description}`;
  return cloned;
}

function summarise(rules) {
  const counts = new Map();
  for (const rule of rules) {
    const key = String(rule.load_test_base_rule_id || "unknown");
    counts.set(key, (counts.get(key) || 0) + 1);
  }

  return Array.from(counts.entries())
    .sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    })
    .map(([ruleID, count]) => ({ rule_id: ruleID, count }));
}

function main() {
  const args = parseArgs(process.argv);
  const sourceRules = readRules(SOURCE_RULES_FILE);
  const batchLabel = makeBatchLabel();
  const distribution = buildDistribution(sourceRules, args.total, args.hotRuleId, args.hotCount);
  const outputRules = distribution.map((rule, index) => createLoadTestRule(rule, index + 1, batchLabel));

  ensureDirectory(path.dirname(args.output));
  fs.writeFileSync(args.output, `${JSON.stringify(outputRules, null, 2)}\n`, "utf8");

  const summary = summarise(outputRules);
  console.log(JSON.stringify({
    output_file: path.relative(REPO_ROOT, args.output).replace(/\\/g, "/"),
    total_rules: outputRules.length,
    hot_rule_id: args.hotRuleId,
    hot_rule_count: args.hotCount,
    load_test_batch: batchLabel,
    top_templates: summary.slice(0, 10),
  }, null, 2));
}

main();
