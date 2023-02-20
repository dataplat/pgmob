DO
$$
BEGIN
    COPY command_output(msg) FROM PROGRAM %s WITH DELIMITER e'\x03';
END;
$$
language plpgsql;