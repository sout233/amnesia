import { supabase } from '$lib/supabaseClient';
import { hashPassword, verifyRegisterInviteCode } from '$lib/crypto/appCrypto';
import type { EntityId, LoginPayload, RegisterPayload, SystemRole, UserProfile } from '$lib/types/domain';

type RawUserRow = {
	id: string;
	username: string;
	password_hash?: string | null;
	password?: string | null;
	system_role: SystemRole;
	encryption_key_hint?: string | null;
	encryption_notice_accepted?: boolean;
	created_at?: string;
};

function mapUser(row: RawUserRow): UserProfile {
	return {
		id: row.id,
		username: row.username,
		systemRole: row.system_role,
		encryptionReady: !!row.encryption_key_hint,
		encryptionNoticeAccepted: !!row.encryption_notice_accepted,
		createdAt: row.created_at
	};
}

export async function loginWithPassword(payload: LoginPayload) {
	const passwordHash = await hashPassword(payload.password);
	const { data, error } = await supabase
		.from('amnesia_users')
		.select('id, username, password_hash, password, system_role, encryption_key_hint, encryption_notice_accepted, created_at')
		.eq('username', payload.username)
		.maybeSingle();

	if (error) throw error;
	if (!data) return null;
	const user = data as RawUserRow;
	const legacyPasswordMatched = !!user.password && user.password === payload.password;
	const hashedPasswordMatched = !!user.password_hash && user.password_hash === passwordHash;
	if (!legacyPasswordMatched && !hashedPasswordMatched) {
		return null;
	}
	if (!user.password_hash && legacyPasswordMatched) {
		await supabase
			.from('amnesia_users')
			.update({
				password_hash: passwordHash,
				password: null
			})
			.eq('id', user.id);
	}
	return mapUser({
		...user,
		password_hash: passwordHash
	});
}

export async function registerWithInvite(payload: RegisterPayload) {
	if (!verifyRegisterInviteCode(payload.inviteCode)) {
		return { success: false, message: '邀请码不正确' };
	}

	const { data: existing } = await supabase
		.from('amnesia_users')
		.select('id')
		.eq('username', payload.username)
		.maybeSingle();

	if (existing) {
		return { success: false, message: '该用户名已存在' };
	}

	const passwordHash = await hashPassword(payload.password);
	const { error } = await supabase.from('amnesia_users').insert({
		username: payload.username,
		password_hash: passwordHash,
		system_role: payload.systemRole ?? '用户'
	});

	if (error) {
		return { success: false, message: `注册失败: ${error.message}` };
	}

	return { success: true, message: '注册成功，请登录' };
}

export async function registerUserByAdmin(input: {
	username: string;
	password: string;
	systemRole: SystemRole;
}) {
	return registerWithInvite({
		username: input.username,
		password: input.password,
		inviteCode: 'sout114514',
		systemRole: input.systemRole
	});
}

export async function setUserEncryptionReady(userId: EntityId, keyHint: string) {
	const { error } = await supabase
		.from('amnesia_users')
		.update({
			encryption_key_hint: keyHint,
			encryption_notice_accepted: true
		})
		.eq('id', userId);

	if (error) throw error;
}

export async function listSystemUsers() {
	const { data, error } = await supabase
		.from('amnesia_users')
		.select('id, username, system_role, encryption_key_hint, created_at')
		.order('created_at', { ascending: true });

	if (error) throw error;
	return ((data ?? []) as RawUserRow[]).map(mapUser);
}

export async function removeSystemUser(username: string) {
	const { error } = await supabase.from('amnesia_users').delete().eq('username', username);

	if (error) {
		return { success: false, message: `删除用户失败: ${error.message}` };
	}

	return { success: true, message: '用户已成功删除' };
}
