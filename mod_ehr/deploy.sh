LAYER_DIR="layers/python/lib/python3.11/site-packages/"
echo "Current working directory $PWD"
echo "Creating layers directory"
if [ -d "$LAYER_DIR" ]; then
    rm -rf "$LAYER_DIR"
fi
mkdir -p $LAYER_DIR

echo "Changing Directory to lambda_functions"
cd lambda_functions/
echo "Installing requirements"
pip install -t ../$LAYER_DIR -r requirements.txt --implementation cp --only-binary=:all: --no-cache-dir --upgrade --platform manylinux2014_x86_64 --python-version 3.11
cd ../layers
echo "Zipping layers"
zip -r ../requirements.zip * -x "*/__pycache__/*"
rm -rf python/lib/
echo "zipping health_conector_base"
cp -r ../lambda_functions/health_connector_base python/
zip -r ../health_connector_base.zip * -x "*/__pycache__/*"
echo "$PWD"
cd ../
cd dashboard_website