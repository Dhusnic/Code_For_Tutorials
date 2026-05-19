package rules

// ConditionNode is one node in the nested rule condition tree.
type ConditionNode interface {
	isConditionNode()
}

// RuleCondition is one leaf condition in a rule.
type RuleCondition struct {
	Field         string
	Op            string
	Value         any
	CaseSensitive bool
}

func (RuleCondition) isConditionNode() {}

// RuleConditionGroup is a logical AND/OR group.
type RuleConditionGroup struct {
	Op         string
	Conditions []ConditionNode
}

func (RuleConditionGroup) isConditionNode() {}

type compiledCondition struct {
	Field   string
	Matches func(event map[string]any) bool
	Cost    int
}

func (compiledCondition) isConditionNode() {}

type compiledConditionGroup struct {
	Op            string
	Conditions    []ConditionNode
	Cost          int
	MaxMatchCount int
}

func (compiledConditionGroup) isConditionNode() {}

// SignalRule is one in-memory rule.
type SignalRule struct {
	RuleID      string
	SignalKey   string
	Level       string
	Description string
	Condition   ConditionNode
	Tags        []string
	Vendor      string
}

// RuleSet is the rule collection for one service.
type RuleSet struct {
	Service             string
	Rules               []SignalRule
	HasVendorAwareRules bool
}
