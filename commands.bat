@echo off
echo Running commands to setup the layer...
mkdir common\python\health_connector_base
mkdir common\python\lib\python3.11\site-packages
copy lambda_functions\health_connector_base\* common\python\health_connector_base\
pip install -r lambda_functions\requirements.txt --target common\python\lib\python3.11\site-packages
cd common
tar.exe -a -cf python.zip python
cd ..
rmdir /S /Q common\python
