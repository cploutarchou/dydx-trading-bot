package middleware

import "github.com/gin-gonic/gin"

type requestLogContext struct {
	TraceID    string
	Method     string
	Path       string
	Route      string
	Handler    string
	ClientIP   string
	ErrorCount int
	LastError  string
}

func buildRequestLogContext(c *gin.Context) requestLogContext {
	ctx := requestLogContext{}
	if c == nil {
		return ctx
	}

	ctx.TraceID = GetTraceID(c)
	ctx.Method = c.Request.Method
	ctx.Path = c.Request.URL.Path
	ctx.Route = c.FullPath()
	if ctx.Route == "" {
		ctx.Route = ctx.Path
	}
	ctx.Handler = c.HandlerName()
	if ctx.Handler == "" {
		ctx.Handler = "unknown"
	}
	ctx.ClientIP = c.ClientIP()
	ctx.ErrorCount = len(c.Errors)
	if ctx.ErrorCount > 0 {
		ctx.LastError = c.Errors.Last().Error()
	}

	return ctx
}
