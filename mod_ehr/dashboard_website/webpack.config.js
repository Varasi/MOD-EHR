const path = require("path");
const webpack = require('webpack');
const CopyWebpackPlugin = require("copy-webpack-plugin");

module.exports = (env) => {
    return {
        entry: {
            index: "./src/index.js",
            dashboard: "./src/dashboard.js",
            appointments: "./src/appointments.js",
            patients: "./src/patients.js",
            common: "./src/common.js",
            usermanagement: "./src/usermanagement.js",
            settingspanel: "./src/settingspanel.js",
            logs: "./src/logs.js"
        },
        output: {
            filename: "[name].js",
            path: path.resolve(__dirname, "dist"),
        },

        plugins: [

            new webpack.DefinePlugin({
                'process.env': JSON.stringify(env),
                'process.env.ENV': JSON.stringify(env.ENV || "LOCAL"),
                // 'process.env': {
                //     'ENV': JSON.stringify(env.ENV || "LOCAL"),
                //     'REGION': JSON.stringify(env.REGION || "ap-south-1"),
                //     'POOL_ID': JSON.stringify(env.POOL_ID || "ap-south-1_qs5AAL8nM"),
                //     'CLIENT_ID': JSON.stringify(env.CLIENT_ID || "qkp3u5nbh4ks12m0qkomlajpe"),
                //     'IDENTITY_POOL_ID': JSON.stringify(env.IDENTITY_POOL_ID || "ap-south-1:8c0c6f69-c43f-4e41-874b-709042d61e49"),
                //     'GOOGLE_MAPS_KEY': JSON.stringify(env.GOOGLE_MAPS_KEY || "AIzaSyANCIsb2avj0G07Cdvb3LMcAsgK1coFE54"),
                //     'BASE_URL': JSON.stringify(env.BASE_URL || "https://g7cy1inwui.execute-api.ap-south-1.amazonaws.com")
                // }
            }),

            new CopyWebpackPlugin({
                patterns: [{ from: "src", to: path.resolve(__dirname, "dist") }],
            }),
        ],
        mode: "production",
    }
};
