LAYER_DIR="layers/python/"
if [ -d "$LAYER_DIR" ]; then
    rm -rf "$LAYER_DIR"
fi
mkdir -p $LAYER_DIR
cd layers/
echo "zipping health_conector_base"
cp -r ../lambda_functions/health_connector_base python/
zip -r ../health_connector_base.zip * -x "*/__pycache__/*"