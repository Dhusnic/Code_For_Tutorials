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

// SignalRule is one in-memory rule.
type SignalRule struct {
	RuleID      string
	SignalKey   string
	Level       string
	Description string
	Condition   ConditionNode
	Tags        []string
}

// RuleSet is the rule collection for one service.
type RuleSet struct {
	Service string
	Rules   []SignalRule
}
