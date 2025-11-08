#!/bin/bash
# =============================================================================
# SSL Certificate Generation Script for dYdX Trading Bot
# =============================================================================
# This script generates self-signed certificates for development
# For production, replace with Let's Encrypt or commercial certificates
# =============================================================================

set -e

# Configuration
DOMAIN=${DOMAIN:-localhost}
COUNTRY="US"
STATE="CA"
CITY="San Francisco"
ORG="dYdX Trading Bot"
OU="Development"
EMAIL="admin@${DOMAIN}"

# Certificate paths
CERT_DIR="$(dirname "$0")"
PRIVATE_KEY="${CERT_DIR}/private.key"
CERTIFICATE="${CERT_DIR}/cert.pem"
CSR_FILE="${CERT_DIR}/cert.csr"

echo "============================================================"
echo "🔐 SSL Certificate Generation for dYdX Trading Bot"
echo "============================================================"
echo "Domain: ${DOMAIN}"
echo "Certificate Directory: ${CERT_DIR}"
echo "============================================================"

# Check if certificates already exist
if [[ -f "${PRIVATE_KEY}" && -f "${CERTIFICATE}" ]]; then
    echo "⚠️  SSL certificates already exist:"
    echo "   Private Key: ${PRIVATE_KEY}"
    echo "   Certificate: ${CERTIFICATE}"
    echo ""
    read -p "Do you want to regenerate them? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Using existing certificates"
        exit 0
    fi
    echo "🔄 Regenerating certificates..."
fi

# Generate private key
echo "🔑 Generating private key..."
openssl genrsa -out "${PRIVATE_KEY}" 2048
chmod 600 "${PRIVATE_KEY}"

# Generate certificate signing request
echo "📝 Generating certificate signing request..."
openssl req -new \
    -key "${PRIVATE_KEY}" \
    -out "${CSR_FILE}" \
    -subj "/C=${COUNTRY}/ST=${STATE}/L=${CITY}/O=${ORG}/OU=${OU}/CN=${DOMAIN}/emailAddress=${EMAIL}"

# Generate self-signed certificate
echo "🏆 Generating self-signed certificate..."
openssl x509 -req \
    -days 365 \
    -in "${CSR_FILE}" \
    -signkey "${PRIVATE_KEY}" \
    -out "${CERTIFICATE}" \
    -extensions v3_req \
    -extfile <(cat << EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${DOMAIN}
DNS.2 = *.${DOMAIN}
DNS.3 = localhost
DNS.4 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF
)

# Set proper permissions
chmod 644 "${CERTIFICATE}"
chmod 600 "${PRIVATE_KEY}"

# Clean up CSR file
rm -f "${CSR_FILE}"

echo "============================================================"
echo "✅ SSL Certificate Generated Successfully!"
echo "============================================================"
echo "Private Key: ${PRIVATE_KEY}"
echo "Certificate: ${CERTIFICATE}"
echo ""
echo "Certificate Details:"
openssl x509 -in "${CERTIFICATE}" -text -noout | grep -A 2 "Subject:"
openssl x509 -in "${CERTIFICATE}" -text -noout | grep -A 10 "X509v3 Subject Alternative Name:"
echo ""
echo "Valid Until:"
openssl x509 -in "${CERTIFICATE}" -enddate -noout

echo ""
echo "============================================================"
echo "🚀 Next Steps:"
echo "============================================================"
echo "1. For development:"
echo "   - Use the generated self-signed certificates"
echo "   - Accept security warnings in browser"
echo ""
echo "2. For production:"
echo "   - Replace with Let's Encrypt certificates:"
echo "     certbot certonly --standalone -d ${DOMAIN}"
echo "   - Or use commercial SSL certificates"
echo ""
echo "3. Update docker-compose.yml if domain changed:"
echo "   - Set DOMAIN=${DOMAIN} in .env.docker"
echo ""
echo "4. Trust the certificate (development only):"
echo "   - macOS: Add cert.pem to Keychain Access"
echo "   - Linux: Add to /usr/local/share/ca-certificates/"
echo "   - Windows: Import to Trusted Root Certification Authorities"
echo "============================================================"