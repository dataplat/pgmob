command=$(cat <<EOF
em=\$({command} 2>&1; r=\$?; echo /; exit "\$r")
printf "\$?\n"
printf "\${{em%/}}" | sed 's/\\r/\\\\r/g'
EOF
)
bash -o pipefail -c "$command"