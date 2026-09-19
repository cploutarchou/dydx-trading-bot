package app

import (
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestTrustedProxiesFromEnv(t *testing.T) {
	cases := []struct {
		name    string
		raw     string
		want    []string
		wantErr bool
	}{
		{name: "unset keeps loopback only", raw: "", want: []string{"127.0.0.1", "::1"}},
		{name: "pod CIDR and single IP", raw: " 10.42.0.0/16 , 192.168.1.10 ", want: []string{"127.0.0.1", "::1", "10.42.0.0/16", "192.168.1.10"}},
		{name: "invalid CIDR rejects the whole list", raw: "10.42.0.0/16,10.0.0.0/99", want: []string{"127.0.0.1", "::1"}, wantErr: true},
		{name: "hostname is not accepted", raw: "traefik.local", want: []string{"127.0.0.1", "::1"}, wantErr: true},
		{name: "trust-everything is refused", raw: "0.0.0.0/0", want: []string{"127.0.0.1", "::1"}, wantErr: true},
		{name: "ipv6 trust-everything is refused", raw: "::/0", want: []string{"127.0.0.1", "::1"}, wantErr: true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := trustedProxiesFromEnv(tc.raw)
			if (err != nil) != tc.wantErr {
				t.Fatalf("err = %v, wantErr %v", err, tc.wantErr)
			}
			if !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

// A forwarded header is honoured only when the direct peer is a trusted proxy.
func TestClientIPHonoursForwardedHeaderOnlyFromTrustedProxy(t *testing.T) {
	gin.SetMode(gin.TestMode)
	proxies, err := trustedProxiesFromEnv("10.42.0.0/16")
	if err != nil {
		t.Fatal(err)
	}
	router := gin.New()
	if err := router.SetTrustedProxies(proxies); err != nil {
		t.Fatal(err)
	}
	router.GET("/ip", func(c *gin.Context) { c.String(http.StatusOK, c.ClientIP()) })

	clientIP := func(remoteAddr string) string {
		req := httptest.NewRequest(http.MethodGet, "/ip", nil)
		req.RemoteAddr = remoteAddr
		req.Header.Set("X-Forwarded-For", "203.0.113.7")
		res := httptest.NewRecorder()
		router.ServeHTTP(res, req)
		return res.Body.String()
	}

	if got := clientIP("10.42.1.5:40000"); got != "203.0.113.7" {
		t.Fatalf("behind the ingress: client IP = %q, want the forwarded address", got)
	}
	if got := clientIP("198.51.100.9:40000"); got != "198.51.100.9" {
		t.Fatalf("untrusted peer spoofing the header: client IP = %q, want the peer address", got)
	}
}
