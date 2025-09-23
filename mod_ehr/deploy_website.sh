REGION="ap-south-1"
POOL_ID="ap-south-1_qs5AAL8nM"
CLIENT_ID="qkp3u5nbh4ks12m0qkomlajpe"
IDENTITY_POOL_ID="ap-south-1:8c0c6f69-c43f-4e41-874b-709042d61e49"
GOOGLE_MAPS_KEY="AIzaSyANCIsb2avj0G07Cdvb3LMcAsgK1coFE54"
BASE_URL="https://g7cy1inwui.execute-api.ap-south-1.amazonaws.com"
cd dashboard_website
npx webpack --env REGION=$REGION POOL_ID=$POOL_ID CLIENT_ID=$CLIENT_ID  IDENTITY_POOL_ID=$IDENTITY_POOL_ID GOOGLE_MAPS_KEY=$GOOGLE_MAPS_KEY BASE_URL=$BASE_URL
 
