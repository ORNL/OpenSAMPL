# Setting up Automatic Ingestion

If you want to automatically ingest files to your openSAMPL database, the easiest way to do that is via CRON

1. open crontab using `crontab -e`
2. add the line with instructions for your job: 
```
2-59/5 * * * * opensampl load ADVA /path/to/data/dir >> /path/to/logfile.log 2>&1 
```

