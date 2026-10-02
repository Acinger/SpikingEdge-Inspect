#!/bin/bash
# ============================================================
# VORSA - Akida-PCIe-Treiber reproduzierbar bauen (Kernel 6.12)
# Der offizielle Treiber (Brainchip-Inc/akida_dw_edma) kennt nur
# Kernel bis 6.8; fuer den Pi-5-Kernel 6.12 braucht es zwei Patches.
# Genau die wurden am 2026-09-06 haendisch gefunden - hier fest.
# Aufruf auf dem Pi:  bash setup_akida_treiber.sh
# ============================================================
set -e
cd ~
if [ ! -d akida_dw_edma ]; then
  git clone https://github.com/Brainchip-Inc/akida_dw_edma
fi
cd akida_dw_edma

# Patch 1: DKMS-Kernelschranke entfernen
sed -i '/BUILD_EXCLUSIVE_KERNEL/d' dkms.conf

# Patch 2: Makefile-Abbruch fuer >6.9 durch den 6.9-Zweig ersetzen
python3 - <<'PY'
p="Makefile"; s=open(p).read()
alt=("else\n$(error Kernel $(VERSION).$(PATCHLEVEL) not supported. "
     "Some incompatibilities can be present)\nendif")
neu=("else\nccflags-y += -I$(src)/kernel/5.16/drivers/dma\n"
     "akida-pcie-y += akida-dw-edma/dw-edma-core.o\n"
     "akida-pcie-y += akida-dw-edma/dw-edma-v0-core.o\n"
     "akida-pcie-y += akida-dw-edma/dw-edma-v0-debugfs.o\n"
     "akida-pcie-y += akida-dw-edma/dw-hdma-v0-core.o\n"
     "akida-pcie-y += akida-dw-edma/dw-hdma-v0-debugfs.o\nendif")
if alt in s:
    open(p,"w").write(s.replace(alt,neu,1)); print("Makefile gepatcht")
else:
    print("Makefile-Muster nicht gefunden - evtl. schon gepatcht")
PY

sudo ./install.sh

# Modul beim Booten automatisch laden (sonst nur per udev, was bei
# schon eingesteckten Karten manchmal nicht greift)
echo "akida-pcie" | sudo tee /etc/modules-load.d/akida-pcie.conf >/dev/null
sudo modprobe akida-pcie || true

echo "----"
echo "Fertig. Karten pruefen:"
echo "  source ~/akida-env/bin/activate && python3 -c 'import akida; print(akida.devices())'"
