#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

SDK_ROOT="/home/rootkit/Android/Sdk"
BUILD_TOOLS="$SDK_ROOT/build-tools/35.0.0"
PLATFORM="$SDK_ROOT/platforms/android-35"
if [ ! -f "$PLATFORM/android.jar" ]; then
    PLATFORM="$SDK_ROOT/platforms/android-34"
fi

JAVA_HOME="/home/rootkit/.local/share/java/jdk-21.0.12.1+1"
export PATH="$JAVA_HOME/bin:$PATH"

echo "⚙️ Preparando entorno de compilación..."
rm -rf build/gen build/obj build/apk
mkdir -p build/gen build/obj build/apk

echo "📦 Compilando recursos con aapt2..."
$BUILD_TOOLS/aapt2 compile --dir res -o build/resources.zip
$BUILD_TOOLS/aapt2 link -I "$PLATFORM/android.jar" \
    --manifest AndroidManifest.xml \
    -o build/apk/unaligned.apk \
    --java build/gen \
    --auto-add-overlay \
    build/resources.zip

echo "☕ Compilando código Java con javac (--release 8)..."
javac -cp "$PLATFORM/android.jar" --release 8 -d build/obj \
    $(find build/gen -name "*.java") \
    $(find src -name "*.java")

echo "⚡ Convirtiendo bytecode a DEX con d8..."
$BUILD_TOOLS/d8 --output build/apk/ --lib "$PLATFORM/android.jar" --min-api 26 \
    $(find build/obj -name "*.class")

echo "📦 Empaquetando classes.dex y assets..."
mkdir -p build/apk/assets
cp "$DIR/scanner.html" build/apk/assets/scanner.html
cd build/apk
jar -uf unaligned.apk classes.dex assets/scanner.html

echo "📐 Alineando APK con zipalign..."
$BUILD_TOOLS/zipalign -f -p 4 unaligned.apk aligned.apk

echo "🔑 Firmando APK con apksigner..."
if [ ! -f ../debug.keystore ]; then
    keytool -genkey -v -keystore ../debug.keystore \
        -alias androiddebugkey -storepass android -keypass android \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -dname "CN=PocketController,O=Camilo,C=CO"
fi

$BUILD_TOOLS/apksigner sign --ks ../debug.keystore \
    --ks-pass pass:android --key-pass pass:android \
    --ks-key-alias androiddebugkey \
    --out PocketController.apk aligned.apk

$BUILD_TOOLS/apksigner verify PocketController.apk

cp PocketController.apk "$DIR/../PocketController.apk"
cp PocketController.apk "$DIR/../web/PocketController.apk"

echo "✅ Compilación exitosa: $DIR/../web/PocketController.apk"
