INSERT INTO dbo.Users (Username, PasswordHash)
	VALUES ('Admin Rea', 'scrypt:32768:8:1$TsWSINAtPHrDyyrM$3022a13176dc627edfa4b12813b2a093dc6d7eeacbc7ce54227d8320d6779eeb0cdf9bb945d8cdbe982db97c5cc128504988f7cdbe896805063a192fa7f6dba9');

-- The hash above is a werkzeug scrypt hash of the password 'pass123'.
-- New users registered through /signup are stored using the same secure hashing.