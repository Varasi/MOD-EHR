import { importSPKI, exportJWK } from 'jose';
import fs from 'fs';

// Read your PEM public key from a file
const pem = fs.readFileSync('ssh_keys/publickey.pem', 'utf8');

// Import the PEM public key
const publicKey = await importSPKI(pem, 'RS256');

// Convert to JWKS format
const jwk = await exportJWK(publicKey);

// Add a 'kid' (Key ID) to the key.
jwk.kid = "hospital1003"

// Output JWKS
const jwks = { keys: [jwk] };
console.log(JSON.stringify(jwks, null, 2));

if (!fs.existsSync('jwks-files')) {
  fs.mkdirSync('jwks-files');
}
fs.writeFileSync('jwks-files/jwks.json', JSON.stringify(jwks, null, 2));
console.log('JWKS written to jwks.json');

//add kid in the pucblic ket set and also in the jwt header