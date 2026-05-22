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
	avatar_seed?: string | null;
	avatar_url?: string | null;
};

function mapUser(row: RawUserRow): UserProfile {
	return {
		id: row.id,
		username: row.username,
		systemRole: row.system_role,
		encryptionReady: !!row.encryption_key_hint,
		encryptionNoticeAccepted: !!row.encryption_notice_accepted,
		createdAt: row.created_at,
		avatarSeed: row.avatar_seed ?? null,
		avatarUrl: row.avatar_url ?? null
	};
}

export async function loginWithPassword(payload: LoginPayload) {
	const passwordHash = await hashPassword(payload.password);
	const { data, error } = await supabase
		.from('amnesia_users')
		.select('id, username, password_hash, password, system_role, encryption_key_hint, encryption_notice_accepted, created_at, avatar_seed, avatar_url')
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
		avatar_seed: payload.username,
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
		.select('id, username, system_role, encryption_key_hint, created_at, avatar_seed, avatar_url')
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

export async function updateUserAvatar(input: {
	userId: EntityId;
	avatarSeed?: string | null;
	avatarUrl?: string | null;
}) {
	const patch: Record<string, unknown> = {};
	if (input.avatarSeed !== undefined) patch.avatar_seed = input.avatarSeed;
	if (input.avatarUrl !== undefined) patch.avatar_url = input.avatarUrl;

	let updateError: { message?: string; code?: string } | null = null;

	if (Object.keys(patch).length > 0) {
		const primary = await supabase
			.from('amnesia_users')
			.update(patch)
			.eq('id', input.userId)
			.select('id, username, system_role, encryption_key_hint, encryption_notice_accepted, created_at, avatar_seed, avatar_url')
			.single();

		if (!primary.error) {
			return mapUser(primary.data as RawUserRow);
		}

		updateError = primary.error;

		// 兼容数据库 schema cache 尚未包含 avatar_seed 的情况：
		// 先只更新 avatar_url，至少保证自定义头像可以正常工作。
		if (
			(updateError.code === 'PGRST204' || updateError.code === 'PGRST205') &&
			typeof updateError.message === 'string' &&
			updateError.message.includes('avatar_seed') &&
			input.avatarUrl !== undefined
		) {
			const fallback = await supabase
				.from('amnesia_users')
				.update({
					avatar_url: input.avatarUrl
				})
				.eq('id', input.userId)
				.select('id, username, system_role, encryption_key_hint, encryption_notice_accepted, created_at, avatar_url')
				.single();

			if (!fallback.error) {
				return mapUser({
					...(fallback.data as RawUserRow),
					avatar_seed: input.avatarSeed ?? null
				});
			}

			updateError = fallback.error;
		}
	}

	if (updateError) throw updateError;

	const { data, error } = await supabase
		.from('amnesia_users')
		.select('id, username, system_role, encryption_key_hint, encryption_notice_accepted, created_at, avatar_seed, avatar_url')
		.eq('id', input.userId)
		.single();

	if (error) throw error;
	return mapUser(data as RawUserRow);
}
