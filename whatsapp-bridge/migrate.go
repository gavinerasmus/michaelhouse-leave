package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	sqlcipher "github.com/mutecomm/go-sqlcipher/v4"
)

// MigrateToEncrypted converts an existing unencrypted SQLite database to encrypted format
func MigrateToEncrypted(unencryptedPath, encryptedPath, key string) error {
	// Check if unencrypted database exists
	if _, err := os.Stat(unencryptedPath); os.IsNotExist(err) {
		return fmt.Errorf("unencrypted database does not exist: %s", unencryptedPath)
	}

	// Check if database is already encrypted
	if encrypted, err := sqlcipher.IsEncrypted(unencryptedPath); err != nil {
		return fmt.Errorf("failed to check if database is encrypted: %v", err)
	} else if encrypted {
		return fmt.Errorf("database is already encrypted: %s", unencryptedPath)
	}

	// Create backup of original database
	backupPath := unencryptedPath + ".backup"
	if err := copyFile(unencryptedPath, backupPath); err != nil {
		return fmt.Errorf("failed to create backup: %v", err)
	}
	fmt.Printf("Created backup: %s\n", backupPath)

	// Open unencrypted database
	unencryptedDB, err := sql.Open("sqlite3", unencryptedPath)
	if err != nil {
		return fmt.Errorf("failed to open unencrypted database: %v", err)
	}
	defer unencryptedDB.Close()

	// Create encrypted database path
	if err := os.MkdirAll(filepath.Dir(encryptedPath), 0755); err != nil {
		return fmt.Errorf("failed to create directory: %v", err)
	}

	// Build encrypted DSN
	encryptedDSN := buildEncryptedDSN(encryptedPath, key)

	// Attach encrypted database
	attachQuery := fmt.Sprintf("ATTACH DATABASE '%s' AS encrypted KEY '%s'", encryptedDSN, key)
	if _, err := unencryptedDB.Exec(attachQuery); err != nil {
		return fmt.Errorf("failed to attach encrypted database: %v", err)
	}

	// Export to encrypted database using sqlcipher_export
	if _, err := unencryptedDB.Exec("SELECT sqlcipher_export('encrypted')"); err != nil {
		return fmt.Errorf("failed to export to encrypted database: %v", err)
	}

	// Detach database
	if _, err := unencryptedDB.Exec("DETACH DATABASE encrypted"); err != nil {
		return fmt.Errorf("failed to detach database: %v", err)
	}

	// Verify encrypted database was created and is encrypted
	if encrypted, err := sqlcipher.IsEncrypted(encryptedPath); err != nil {
		return fmt.Errorf("failed to verify encrypted database: %v", err)
	} else if !encrypted {
		return fmt.Errorf("migration failed - database is not encrypted")
	}

	fmt.Printf("Successfully migrated to encrypted database: %s\n", encryptedPath)
	fmt.Printf("Original database backed up to: %s\n", backupPath)
	fmt.Printf("You can delete the original unencrypted database after verifying the migration\n")

	return nil
}

// copyFile copies a file from src to dst
func copyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer destFile.Close()

	if _, err := destFile.ReadFrom(sourceFile); err != nil {
		return err
	}

	return destFile.Sync()
}

// MigrateDatabases helps migrate existing databases to encrypted format
func MigrateDatabases() error {
	fmt.Println("=== WhatsApp MCP Database Encryption Migration ===")
	fmt.Println()

	// Check if unencrypted databases exist
	messagesDB := "store/messages.db"
	whatsappDB := "store/whatsapp.db"

	var needsMigration []string

	if _, err := os.Stat(messagesDB); err == nil {
		if encrypted, err := sqlcipher.IsEncrypted(messagesDB); err == nil && !encrypted {
			needsMigration = append(needsMigration, messagesDB)
		}
	}

	if _, err := os.Stat(whatsappDB); err == nil {
		if encrypted, err := sqlcipher.IsEncrypted(whatsappDB); err == nil && !encrypted {
			needsMigration = append(needsMigration, whatsappDB)
		}
	}

	if len(needsMigration) == 0 {
		fmt.Println("No unencrypted databases found. All databases are already encrypted or don't exist yet.")
		return nil
	}

	fmt.Printf("Found %d unencrypted database(s) that need migration:\n", len(needsMigration))
	for _, db := range needsMigration {
		fmt.Printf("  - %s\n", db)
	}
	fmt.Println()

	// Migrate messages database
	if contains(needsMigration, messagesDB) {
		fmt.Println("Migrating messages database...")
		key, err := getOrCreateEncryptionKey("WHATSAPP_MESSAGES_KEY", "store/.messages_key")
		if err != nil {
			return fmt.Errorf("failed to get messages encryption key: %v", err)
		}

		tempPath := messagesDB + ".encrypted"
		if err := MigrateToEncrypted(messagesDB, tempPath, key); err != nil {
			return fmt.Errorf("failed to migrate messages database: %v", err)
		}

		// Replace original with encrypted version
		if err := os.Rename(tempPath, messagesDB); err != nil {
			return fmt.Errorf("failed to replace messages database: %v", err)
		}
		fmt.Printf("✓ Messages database encrypted successfully\n\n")
	}

	// Migrate session database
	if contains(needsMigration, whatsappDB) {
		fmt.Println("Migrating WhatsApp session database...")
		key, err := getOrCreateEncryptionKey("WHATSAPP_SESSION_KEY", "store/.session_key")
		if err != nil {
			return fmt.Errorf("failed to get session encryption key: %v", err)
		}

		tempPath := whatsappDB + ".encrypted"
		if err := MigrateToEncrypted(whatsappDB, tempPath, key); err != nil {
			return fmt.Errorf("failed to migrate session database: %v", err)
		}

		// Replace original with encrypted version
		if err := os.Rename(tempPath, whatsappDB); err != nil {
			return fmt.Errorf("failed to replace session database: %v", err)
		}
		fmt.Printf("✓ Session database encrypted successfully\n\n")
	}

	fmt.Println("=== Migration Complete ===")
	fmt.Println("All databases are now encrypted with AES-256 encryption.")
	fmt.Println("IMPORTANT: Backup your encryption key files:")
	fmt.Println("  - store/.messages_key")
	fmt.Println("  - store/.session_key")
	fmt.Println("Without these keys, you cannot decrypt your data!")

	return nil
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}