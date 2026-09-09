#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# PS2 Hub — Script de instalação completa (Samba + aria2)
# Execute com: sudo bash setup.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SMB_CONF_SRC="$SCRIPT_DIR/smb.conf"
SMB_CONF_DST="/etc/samba/smb.conf"
ARIA2_CONF="$SCRIPT_DIR/aria2.conf"
DATA_DIR="$SCRIPT_DIR/data"
REAL_USER="${SUDO_USER:-$(whoami)}"

echo "╔══════════════════════════════════════════════════╗"
echo "║      PS2 Hub — Configuração Completa            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Verificar se está rodando como root ─────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "❌ Este script precisa ser executado como root (sudo)."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════
# 1. SAMBA
# ═══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 📁  Configurando Samba..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! command -v smbd &>/dev/null; then
    echo "📦 Instalando Samba..."
    apt-get update -qq
    apt-get install -y -qq samba samba-common > /dev/null
    echo "✅ Samba instalado."
else
    echo "✅ Samba já está instalado."
fi

if [[ -f "$SMB_CONF_DST" ]]; then
    BACKUP="$SMB_CONF_DST.bak.$(date +%Y%m%d%H%M%S)"
    cp "$SMB_CONF_DST" "$BACKUP"
    echo "💾 Backup salvo em: $BACKUP"
fi

cp "$SMB_CONF_SRC" "$SMB_CONF_DST"
echo "📝 Configuração copiada para $SMB_CONF_DST"

mkdir -p /var/log/samba
testparm -s "$SMB_CONF_DST" > /dev/null 2>&1 && echo "✅ Configuração válida." || echo "⚠️  Verifique a configuração."

systemctl restart smbd
systemctl enable smbd
echo "✅ Samba ativo e habilitado na inicialização."
echo ""

# ═══════════════════════════════════════════════════════════════
# 2. ARIA2
# ═══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ⬇️   Configurando aria2c..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! command -v aria2c &>/dev/null; then
    echo "📦 Instalando aria2..."
    apt-get update -qq
    apt-get install -y -qq aria2 > /dev/null
    echo "✅ aria2 instalado."
else
    echo "✅ aria2 já está instalado."
fi

# Criar diretórios e arquivo de sessão
mkdir -p "$DATA_DIR/downloads"
touch "$DATA_DIR/downloads/aria2.session"
chown -R "$REAL_USER:$REAL_USER" "$DATA_DIR"

# Criar serviço systemd para aria2
cat > /etc/systemd/system/ps2hub-aria2.service << EOF
[Unit]
Description=PS2 Hub — aria2c RPC Daemon
After=network.target

[Service]
Type=forking
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/aria2c --conf-path=$ARIA2_CONF
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ps2hub-aria2.service

# Parar aria2 manual se estiver rodando, depois iniciar via systemd
pkill aria2c 2>/dev/null || true
sleep 1
systemctl start ps2hub-aria2.service

echo "✅ aria2c ativo como serviço systemd (ps2hub-aria2)."
echo ""

# ═══════════════════════════════════════════════════════════════
# 3. PERMISSÕES DA PASTA DATA
# ═══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 🔒  Ajustando permissões..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
chown -R "$REAL_USER:$REAL_USER" "$DATA_DIR"
chmod -R 775 "$DATA_DIR"
echo "✅ Permissões ajustadas para $DATA_DIR"
echo ""

# ═══════════════════════════════════════════════════════════════
# 4. SUDOERS (permitir controle de serviços via interface web)
# ═══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 🔑  Configurando permissões sudoers..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SUDOERS_FILE="/etc/sudoers.d/ps2hub-services"
cat > "$SUDOERS_FILE" << EOF
# PS2 Hub — Allow service control without password
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start smbd
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop smbd
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart smbd
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start ps2hub-aria2
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop ps2hub-aria2
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart ps2hub-aria2
EOF
chmod 440 "$SUDOERS_FILE"
visudo -cf "$SUDOERS_FILE" > /dev/null 2>&1 && echo "✅ Regras sudoers configuradas." || echo "⚠️  Erro na validação do sudoers."
echo ""

# ═══════════════════════════════════════════════════════════════
# RESUMO
# ═══════════════════════════════════════════════════════════════
IP_ADDR=$(hostname -I | awk '{print $1}')
echo "╔══════════════════════════════════════════════════╗"
echo "║   ✅  PS2 Hub configurado com sucesso!          ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║   Samba:                                         ║"
echo "║     Share: PS2HUB                                ║"
echo "║     Protocolo: SMBv1 (compatível com OPL)        ║"
echo "║     Acesso: Sem senha (guest)                    ║"
echo "║                                                  ║"
echo "║   aria2c:                                        ║"
echo "║     Serviço: ps2hub-aria2 (systemd)              ║"
echo "║     RPC: http://localhost:6800/jsonrpc            ║"
echo "║     Secret: ps2hub                               ║"
echo "║                                                  ║"
echo "║   No OPL do PS2, configure:                      ║"
echo "║     Endereço: $IP_ADDR"
echo "║     Share: PS2HUB                                ║"
echo "║     Usuário/Senha: (vazio)                       ║"
echo "╚══════════════════════════════════════════════════╝"
