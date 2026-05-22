const APP_REGISTER_INVITE_CODE = 'sout114514';

export function verifyRegisterInviteCode(code: string) {
	return code.trim() === APP_REGISTER_INVITE_CODE;
}

async function sha256(input: string) {
	const encoder = new TextEncoder();
	const buffer = await crypto.subtle.digest('SHA-256', encoder.encode(input));
	return Array.from(new Uint8Array(buffer))
		.map((byte) => byte.toString(16).padStart(2, '0'))
		.join('');
}

export async function hashPassword(password: string) {
	return sha256(`amnesia::password::${password}`);
}

export async function deriveDocEncryptionKey(password: string) {
	return sha256(`amnesia::doc-key::${password}`);
}

function normalizeAesKey(source: string) {
	return source.padEnd(32, '0').slice(0, 32);
}

function encodeBase64(bytes: Uint8Array) {
	let binary = '';
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary);
}

function decodeBase64(base64: string) {
	return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
}

async function importAesKey(secret: string, usage: 'encrypt' | 'decrypt') {
	return crypto.subtle.importKey(
		'raw',
		new TextEncoder().encode(normalizeAesKey(secret)),
		'AES-GCM',
		false,
		[usage]
	);
}

export async function encryptDocumentContent(plainText: string, password: string) {
	const keyMaterial = await importAesKey(password, 'encrypt');
	const iv = crypto.getRandomValues(new Uint8Array(12));
	const cipherBuffer = await crypto.subtle.encrypt(
		{ name: 'AES-GCM', iv },
		keyMaterial,
		new TextEncoder().encode(plainText)
	);
	return {
		version: 1,
		iv: encodeBase64(iv),
		cipherText: encodeBase64(new Uint8Array(cipherBuffer))
	};
}

export async function decryptDocumentContent(
	cipherText: string,
	iv: string,
	password: string
) {
	const keyMaterial = await importAesKey(password, 'decrypt');
	const buffer = decodeBase64(cipherText);
	const plainBuffer = await crypto.subtle.decrypt(
		{ name: 'AES-GCM', iv: decodeBase64(iv) },
		keyMaterial,
		buffer
	);
	return new TextDecoder().decode(plainBuffer);
}
