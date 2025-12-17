REGION="us-east-1"
POOL_ID="us-east-1_dCo7aAKQk"
CLIENT_ID="22eofn4rjh9l4sdvmfsbg271o5"
IDENTITY_POOL_ID="us-east-1:cf5f0f25-b76d-44bc-b5ce-7d5aa484bc3e"
GOOGLE_MAPS_KEY="AIzaSyANCIsb2avj0G07Cdvb3LMcAsgK1coFE54"
BASE_URL="https://c18fik9rmg.execute-api.us-east-1.amazonaws.com"
cd dashboard_website
npx webpack --env REGION=$REGION POOL_ID=$POOL_ID CLIENT_ID=$CLIENT_ID  IDENTITY_POOL_ID=$IDENTITY_POOL_ID GOOGLE_MAPS_KEY=$GOOGLE_MAPS_KEY BASE_URL=$BASE_URL
 
