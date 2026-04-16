package errors

import "fmt"

type OperationError struct {
	Code    string         `json:"code"`
	Message string         `json:"message"`
	Details map[string]any `json:"details,omitempty"`
	Cause   error          `json:"-"`
}

func (e *OperationError) Error() string {
	if e == nil {
		return ""
	}
	if e.Cause == nil {
		return fmt.Sprintf("%s: %s", e.Code, e.Message)
	}
	return fmt.Sprintf("%s: %s: %v", e.Code, e.Message, e.Cause)
}

func (e *OperationError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Cause
}

func New(code, message string) *OperationError {
	return &OperationError{
		Code:    code,
		Message: message,
	}
}

func Wrap(code, message string, cause error) *OperationError {
	return &OperationError{
		Code:    code,
		Message: message,
		Cause:   cause,
	}
}
