"""
音频格式转换工具
使用ffmpeg将m4a转换为mp3
"""
import os
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

def check_ffmpeg():
    """检查ffmpeg是否可用"""
    return shutil.which('ffmpeg') is not None

def convert_m4a_to_mp3(input_path, output_path=None, quality=5, threads=8):
    """
    将m4a文件转换为mp3
    
    参数:
        input_path: 输入文件路径
        output_path: 输出文件路径（如果为None，则自动生成）
        quality: 音频质量 (0-9, 0最高质量，默认5)
        threads: 使用的线程数（默认8）
    
    返回:
        (success, output_path, error_message)
    """
    if not os.path.exists(input_path):
        return False, None, "输入文件不存在"
    
    if not check_ffmpeg():
        return False, None, "ffmpeg未安装或不在PATH中"
    
    # 如果未指定输出路径，自动生成
    if output_path is None:
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}.mp3"
    
    try:
        # 首先尝试检测可用的mp3编码器
        # 检查ffmpeg支持的编码器
        check_cmd = ['ffmpeg', '-encoders']
        check_result = subprocess.run(
            check_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        # 确定使用哪个mp3编码器
        mp3_encoder = 'libmp3lame'  # 默认
        if check_result.returncode == 0:
            encoders_output = check_result.stdout + check_result.stderr
            if 'libmp3lame' not in encoders_output:
                # 如果没有libmp3lame，尝试使用内置的mp3编码器
                if 'mp3' in encoders_output.lower():
                    mp3_encoder = 'mp3'
                    logger.info("检测到libmp3lame不可用，使用内置mp3编码器")
                else:
                    # 如果mp3编码器都不可用，使用aac作为备选
                    mp3_encoder = 'aac'
                    output_path = output_path.replace('.mp3', '.m4a')
                    logger.warning("mp3编码器不可用，使用aac编码器，输出格式改为m4a")
            else:
                logger.info("使用libmp3lame编码器")
        else:
            # 如果检查失败，先尝试libmp3lame，失败后再尝试mp3
            logger.warning("无法检测编码器，将尝试多种编码器")
        
        # 构建ffmpeg命令
        # -y: 覆盖输出文件
        # -threads: 线程数
        # -i: 输入文件
        # -codec:a: 音频编码器
        # -qscale:a 或 -b:a: 音频质量/比特率
        # -map_metadata 0: 保留元数据
        
        # 根据编码器选择不同的质量参数
        if mp3_encoder == 'libmp3lame':
            # libmp3lame使用qscale
            cmd = [
                'ffmpeg',
                '-y',
                '-threads', str(threads),
                '-i', input_path,
                '-codec:a', 'libmp3lame',
                '-qscale:a', str(quality),
                '-map_metadata', '0',
                output_path
            ]
        elif mp3_encoder == 'mp3':
            # 内置mp3编码器使用比特率
            # quality 0-9 映射到比特率: 0=320k, 5=192k, 9=128k
            bitrate_map = {0: '320k', 1: '256k', 2: '224k', 3: '192k', 4: '192k', 
                          5: '192k', 6: '160k', 7: '128k', 8: '128k', 9: '128k'}
            bitrate = bitrate_map.get(quality, '192k')
            cmd = [
                'ffmpeg',
                '-y',
                '-threads', str(threads),
                '-i', input_path,
                '-codec:a', 'mp3',
                '-b:a', bitrate,
                '-map_metadata', '0',
                output_path
            ]
        else:  # aac
            # aac编码器使用比特率
            bitrate_map = {0: '320k', 1: '256k', 2: '224k', 3: '192k', 4: '192k',
                          5: '192k', 6: '160k', 7: '128k', 8: '128k', 9: '128k'}
            bitrate = bitrate_map.get(quality, '192k')
            cmd = [
                'ffmpeg',
                '-y',
                '-threads', str(threads),
                '-i', input_path,
                '-codec:a', 'aac',
                '-b:a', bitrate,
                '-map_metadata', '0',
                output_path
            ]
        
        # 执行转换，记录详细输出
        logger.info(f"执行ffmpeg命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3600  # 1小时超时
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"转换成功 - 输入: {input_path}, 输出: {output_path}, 编码器: {mp3_encoder}")
            if result.stderr:
                logger.debug(f"ffmpeg stderr输出: {result.stderr}")
            return True, output_path, None
        else:
            # 如果libmp3lame失败，尝试使用内置mp3编码器
            if mp3_encoder == 'libmp3lame':
                logger.warning("libmp3lame编码失败，尝试使用内置mp3编码器")
                bitrate_map = {0: '320k', 1: '256k', 2: '224k', 3: '192k', 4: '192k',
                              5: '192k', 6: '160k', 7: '128k', 8: '128k', 9: '128k'}
                bitrate = bitrate_map.get(quality, '192k')
                cmd_mp3 = [
                    'ffmpeg',
                    '-y',
                    '-threads', str(threads),
                    '-i', input_path,
                    '-codec:a', 'mp3',
                    '-b:a', bitrate,
                    '-map_metadata', '0',
                    output_path
                ]
                logger.info(f"重试ffmpeg命令: {' '.join(cmd_mp3)}")
                result = subprocess.run(
                    cmd_mp3,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3600
                )
                
                if result.returncode == 0 and os.path.exists(output_path):
                    logger.info(f"转换成功（使用内置mp3编码器） - 输入: {input_path}, 输出: {output_path}")
                    return True, output_path, None
            
            error_msg = result.stderr or "转换失败"
            logger.error(f"转换失败 - 输入: {input_path}, 输出: {output_path}")
            logger.error(f"ffmpeg返回码: {result.returncode}")
            logger.error(f"ffmpeg stdout: {result.stdout}")
            logger.error(f"ffmpeg stderr: {result.stderr}")
            return False, None, error_msg
            
    except Exception as e:
        logger.exception(f"转换过程发生异常 - 输入: {input_path}, 输出: {output_path}, 异常: {str(e)}")
        return False, None, f"转换过程出错: {str(e)}"

def get_audio_format(file_path):
    """获取音频文件格式"""
    if not os.path.exists(file_path):
        return None
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.mp3']:
        return 'mp3'
    elif ext in ['.m4a', '.m4b']:
        return 'm4a'
    elif ext in ['.aac']:
        return 'aac'
    else:
        return None

