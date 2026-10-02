#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# VORSA INSPECT - getrennte Trainingsumgebung fuer den M3-Detektor
#
# Warum getrennt (2026-09-07):
#   Der Akida-2.19-Stack (cnn2snn, opencv-python 5, ml-dtypes) verlangt
#   numpy >= 2. Der Server-Kern braucht aber numpy < 2, weil
#   picamera2/simplejpeg ein System-Binary gegen numpy 1.x ist. Beides in
#   EINEM venv zu haben, macht wahlweise die Kamera oder das Training kaputt.
#
#   Loesung: der Server bleibt in ~/akida-env (numpy 1.26.4). DIESES Skript
#   baut ein zweites, sauberes venv ~/m3-train-env (numpy 2) allein fuers
#   Training. Der Server ruft es als Unterprozess auf (vorsa/m3_extern.py)
#   und laedt die fertige .fbz danach selbst auf den Chip.
#
# Aufruf (auf dem Pi):
#   bash ~/vorsa-m3/setup_m3_train.sh
#
# Danach einmal pruefen:
#   ~/m3-train-env/bin/python -c "import numpy,cv2,tensorflow,cnn2snn,akida; \
#       print('train-env ok', numpy.__version__)"
# ---------------------------------------------------------------------------
set -e

ENVDIR="${HOME}/m3-train-env"

echo "== VORSA M3-Trainingsumgebung =="
echo "Ziel: ${ENVDIR}"
echo

# 1. Sauberes venv - BEWUSST OHNE --system-site-packages, damit nicht die
#    numpy-1.x-Welt des Systems/akida-env hineinragt.
if [ -d "${ENVDIR}" ]; then
  echo "-> ${ENVDIR} existiert bereits, nutze es weiter."
else
  echo "-> lege venv an (python3.11, isoliert)"
  python3 -m venv "${ENVDIR}"
fi

PY="${ENVDIR}/bin/python"
"${PY}" -m pip install --upgrade pip

# 2. numpy 2 ZUERST festnageln, damit spaetere Pakete es nicht verschieben.
echo "-> numpy 2.1.3 (feste Basis fuer den Akida-2.19-Stack)"
"${PY}" -m pip install --resume-retries 10 --timeout 120 "numpy==2.1.3"

# 3. Der eigentliche Trainings-Stack. Versionen passend zu akida 2.19.3.
#    opencv-python-headless statt -python: kein GUI noetig, weniger Ballast.
echo "-> tensorflow / tf_keras / cnn2snn / akida / opencv (dauert einige Minuten)"
"${PY}" -m pip install --resume-retries 10 --timeout 120 \
  "tensorflow==2.19.0" \
  "tf_keras==2.19.0" \
  "cnn2snn==2.19.3" \
  "akida==2.19.3" \
  "opencv-python-headless"

echo
echo "== Pruefung =="
"${PY}" -c "import numpy,cv2,tensorflow as tf,cnn2snn,akida; \
print('OK  numpy',numpy.__version__,'| cv2',cv2.__version__, \
'| tf',tf.__version__,'| cnn2snn',cnn2snn.__version__,'| akida',akida.__version__)"

echo
echo "Fertig. Der VORSA-Server (in ~/akida-env, numpy<2) findet diese"
echo "Umgebung automatisch unter ${ENVDIR}/bin/python und nutzt sie fuers"
echo "M3-Training. Kein Neustart noetig - der naechste Trainingslauf greift."
