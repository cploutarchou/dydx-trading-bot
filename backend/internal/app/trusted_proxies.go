package app

import (
	"fmt"
	"net"
	"strings"
)

// loopbackProxies is the default: only a proxy on the same host is trusted to
// set X-Forwarded-For.
var loopbackProxies = []string{"127.0.0.1", "::1"}

// trustedProxiesFromEnv parses TRUSTED_PROXIES, a comma-separated list of IPs
// and CIDRs (for example the cluster pod CIDR when the API sits behind an
// ingress controller). Gin only honours X-Forwarded-For from these peers, so
// the client IP used for rate limiting and audit logs is the real one without
// trusting headers from arbitrary callers. Loopback is always included.
//
// Any invalid entry rejects the whole list and returns loopback only: a typo
// must never widen trust.
func trustedProxiesFromEnv(raw string) ([]string, error) {
	proxies := append([]string{}, loopbackProxies...)
	for _, entry := range strings.Split(raw, ",") {
		entry = strings.TrimSpace(entry)
		if entry == "" {
			continue
		}
		if strings.Contains(entry, "/") {
			_, network, err := net.ParseCIDR(entry)
			if err != nil {
				return append([]string{}, loopbackProxies...), fmt.Errorf("TRUSTED_PROXIES: invalid CIDR %q", entry)
			}
			if ones, _ := network.Mask.Size(); ones == 0 {
				return append([]string{}, loopbackProxies...), fmt.Errorf("TRUSTED_PROXIES: %q trusts every address", entry)
			}
		} else if net.ParseIP(entry) == nil {
			return append([]string{}, loopbackProxies...), fmt.Errorf("TRUSTED_PROXIES: invalid IP %q", entry)
		}
		proxies = append(proxies, entry)
	}
	return proxies, nil
}
